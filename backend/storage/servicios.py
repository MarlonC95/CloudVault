"""Proveedor de metadatos y permisos para el flujo de almacenamiento."""

from django.db import ProgrammingError, connections, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from almacenamiento.conexion_negocio import validar_proveedor
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.integracion import (
    ArchivoVerificado, CuotaVigente, DestinoAutorizado, InspeccionObjetoTecnico,
)
from almacenamiento.persistencia import RepositorioCargas
from common.ambito import Ambito, NIVELES_ESCRITURA
from compartir.acceso import acceso_usuario, es_compartida, exigir_edicion
from compartir.models import ESCRITURA
from subscriptions.cuotas import CONSULTA_CUOTA, SinSuscripcionVigente, leer_cuota_organizacion

from .models import Archivo, Carpeta
from subscriptions.models import MiembroOrganizacion


def leer_cuota_desplegada(organizacion_id, using="default"):
    """Usa cuotas; tolera la antigua condición sobre una columna no desplegada."""
    try:
        with transaction.atomic(using=using):
            return leer_cuota_organizacion(organizacion_id, using=using)
    except ProgrammingError as exc:
        if getattr(exc.__cause__, "sqlstate", None) != "42703" or "o.esta_activo" not in str(exc):
            raise
    ahora = timezone.now()
    consulta = CONSULTA_CUOTA.replace("  AND o.esta_activo\n", "")
    with connections[using].cursor() as cursor:
        cursor.execute(consulta, [organizacion_id, ahora, ahora])
        filas = cursor.fetchall()
    if len(filas) != 1:
        raise SinSuscripcionVigente(organizacion_id)
    return filas[0]


class ProveedorStorage:
    using = "default"

    def __init__(self):
        self.bloquear_cuota = RepositorioCargas().unidad_de_trabajo
        # `archivos` no tiene columna de checksum: se recuerda solo entre registrar_archivo y la
        # relectura de autorizar_descarga dentro de la misma confirmación (el puente exige igualdad).
        self._checksums = {}

    def resolver_destino(self, *, solicitante_id, carpeta_id):
        with connections[self.using].cursor() as cursor:
            if carpeta_id is None:
                cursor.execute("SELECT organizacion_id, nivel_rol FROM miembros_organizacion WHERE usuario_id = %s", [solicitante_id])
            else:
                cursor.execute("""SELECT m.organizacion_id, m.nivel_rol, o.tipo FROM miembros_organizacion m
                    JOIN carpetas c ON c.organizacion_id = m.organizacion_id
                    JOIN organizaciones o ON o.id = c.organizacion_id
                    WHERE m.usuario_id = %s AND c.id = %s AND NOT c.en_papelera""", [solicitante_id, carpeta_id])
            filas = cursor.fetchall()
        if len(filas) > 1:
            raise ErrorCarga(CodigoError.VALIDATION_ERROR)
        if filas:
            ambito = Ambito(*filas[0])
            if not ambito.puede_escribir:
                raise PermissionDenied()
            if carpeta_id is not None:
                exigir_edicion(ambito, solicitante_id, carpeta_id=carpeta_id)
            return DestinoAutorizado(solicitante_id, ambito.organizacion_id, carpeta_id)
        return self._destino_compartido(solicitante_id, carpeta_id)

    def _destino_compartido(self, solicitante_id, carpeta_id):
        # La carga compartida se imputa a la cuota de la organización de la carpeta.
        acceso = (acceso_usuario(solicitante_id, carpeta_id=carpeta_id, using=self.using)
                  if carpeta_id is not None else None)
        if acceso is None or acceso.rol != ESCRITURA:
            raise PermissionDenied()
        return DestinoAutorizado(solicitante_id, acceso.organizacion_id, carpeta_id)

    def resolver_destino_organizacion(self, *, solicitante_id, carpeta_id, organizacion_id):
        """Revalida la membresía o el permiso de carpeta en el ámbito solicitado."""
        nivel = MiembroOrganizacion.objects.using(self.using).filter(
            usuario_id=solicitante_id, organizacion_id=organizacion_id,
        ).values_list("nivel_rol", flat=True).first()
        if nivel is None and carpeta_id is not None:
            # Editor externo de una carpeta compartida (p. ej. al confirmar su carga).
            destino = self._destino_compartido(solicitante_id, carpeta_id)
            if destino.organizacion_id != organizacion_id:
                raise ErrorCarga(CodigoError.NO_ENCONTRADO)
            return destino
        if type(nivel) is not int or nivel not in NIVELES_ESCRITURA:
            raise PermissionDenied()
        if carpeta_id is not None:
            if not Carpeta.objects.using(self.using).filter(
                pk=carpeta_id, organizacion_id=organizacion_id, en_papelera=False,
            ).exists():
                raise ErrorCarga(CodigoError.NO_ENCONTRADO)
            if nivel != 0 and es_compartida(organizacion_id, self.using):
                exigir_edicion(Ambito(organizacion_id, nivel, "COMPARTIDO"), solicitante_id, carpeta_id=carpeta_id)
        return DestinoAutorizado(solicitante_id, organizacion_id, carpeta_id)

    def leer_cuota(self, *, organizacion_id):
        try:
            limite, usado, fin = leer_cuota_desplegada(organizacion_id, using=self.using)
        except SinSuscripcionVigente:
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None
        return CuotaVigente(organizacion_id, limite, usado, fin)

    def registrar_archivo(self, *, archivo):
        if not connections[self.using].in_atomic_block:
            raise RuntimeError("La publicación requiere una transacción")
        from .repositorio_papelera import nombre_disponible
        from almacenamiento.errores import ConflictoNombreCarga
        if not nombre_disponible(archivo.organizacion_id, archivo.carpeta_id,
                                 archivo.nombre, using=self.using):
            raise ConflictoNombreCarga()
        Archivo.objects.using(self.using).create(
            id=archivo.archivo_id, organizacion_id=archivo.organizacion_id,
            carpeta_id=archivo.carpeta_id, propietario_id=archivo.solicitante_id,
            nombre=archivo.nombre, clave_s3=archivo.clave_final,
            tamano_bytes=archivo.tamano_bytes, tipo_mime=archivo.tipo_mime,
        )
        self._checksums[archivo.archivo_id] = archivo.checksum_sha256

    def autorizar_descarga(self, *, solicitante_id, archivo_id):
        conexion = connections[self.using]
        bloqueo_miembro = " FOR SHARE OF m" if conexion.in_atomic_block else ""
        bloqueo_archivo = " FOR SHARE OF a" if conexion.in_atomic_block else ""
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""SELECT a.id, a.organizacion_id, a.carpeta_id, a.nombre,
                    a.clave_s3, a.tamano_bytes, a.tipo_mime,
                    (SELECT s.checksum_sha256 FROM sesiones_carga s
                     WHERE s.archivo_id = a.id ORDER BY s.creado_en DESC LIMIT 1),
                    (SELECT m.nivel_rol FROM miembros_organizacion m
                     WHERE m.organizacion_id = a.organizacion_id
                       AND m.usuario_id = %s{bloqueo_miembro}),
                    a.propietario_id, o.tipo
                FROM archivos a LEFT JOIN organizaciones o ON o.id = a.organizacion_id WHERE a.id = %s AND NOT a.en_papelera{bloqueo_archivo}""",
                [solicitante_id, archivo_id],
            )
            fila = cursor.fetchone()
        if fila is None:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)

        id_archivo, organizacion_id, carpeta_id, nombre, clave, tamano, mime, checksum, nivel, propietario_id, tipo = fila
        ambito = Ambito(organizacion_id, nivel, tipo)
        if nivel is not None and not ambito.puede_escribir:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)
        if nivel is None or (ambito.requiere_permiso_recurso and propietario_id != solicitante_id):
            acceso = acceso_usuario(solicitante_id, archivo_id=archivo_id, using=self.using)
            if acceso is None or acceso.organizacion_id != organizacion_id:
                raise ErrorCarga(CodigoError.NO_ENCONTRADO)
            if not acceso.permite_descarga:
                raise ErrorCarga(CodigoError.SIN_PERMISO)

        checksum = self._checksums.pop(archivo_id, None) or checksum
        return ArchivoVerificado(
            id_archivo, solicitante_id, organizacion_id, carpeta_id, nombre, clave, tamano, mime, checksum,
        )

    def inspeccionar_objeto_tecnico(self, *, sesion_id, organizacion_id, clave):
        referenciado = Archivo.objects.using(self.using).filter(clave_s3=clave).exists()
        return InspeccionObjetoTecnico(sesion_id, organizacion_id, clave, referenciado, False)


def crear_servicios():
    """Construye el proveedor sin acceder a base de datos ni S3."""
    return validar_proveedor(ProveedorStorage())
