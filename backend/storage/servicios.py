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
from common.ambito import NIVELES_ESCRITURA
from subscriptions.cuotas import CONSULTA_CUOTA, SinSuscripcionVigente, leer_cuota_organizacion

from .models import Archivo


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
                cursor.execute("""SELECT m.organizacion_id, m.nivel_rol FROM miembros_organizacion m
                    JOIN carpetas c ON c.organizacion_id = m.organizacion_id
                    WHERE m.usuario_id = %s AND c.id = %s AND NOT c.en_papelera""", [solicitante_id, carpeta_id])
            filas = cursor.fetchall()
        if len(filas) > 1:
            raise ErrorCarga(CodigoError.VALIDATION_ERROR)
        if not filas or filas[0][1] not in NIVELES_ESCRITURA:
            raise PermissionDenied()
        return DestinoAutorizado(solicitante_id, filas[0][0], carpeta_id)

    def leer_cuota(self, *, organizacion_id):
        try:
            limite, usado, fin = leer_cuota_desplegada(organizacion_id, using=self.using)
        except SinSuscripcionVigente:
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None
        return CuotaVigente(organizacion_id, limite, usado, fin)

    def registrar_archivo(self, *, archivo):
        if not connections[self.using].in_atomic_block:
            raise RuntimeError("La publicación requiere una transacción")
        Archivo.objects.using(self.using).create(
            id=archivo.archivo_id, organizacion_id=archivo.organizacion_id,
            carpeta_id=archivo.carpeta_id, propietario_id=archivo.solicitante_id,
            nombre=archivo.nombre, clave_s3=archivo.clave_final,
            tamano_bytes=archivo.tamano_bytes, tipo_mime=archivo.tipo_mime,
        )
        self._checksums[archivo.archivo_id] = archivo.checksum_sha256

    def autorizar_descarga(self, *, solicitante_id, archivo_id):
        with connections[self.using].cursor() as cursor:
            cursor.execute("""SELECT a.id, a.organizacion_id, a.carpeta_id, a.nombre,
                    a.clave_s3, a.tamano_bytes, a.tipo_mime,
                    (SELECT s.checksum_sha256 FROM sesiones_carga s
                     WHERE s.archivo_id = a.id ORDER BY s.creado_en DESC LIMIT 1)
                FROM archivos a JOIN miembros_organizacion m ON m.organizacion_id = a.organizacion_id
                WHERE a.id = %s AND m.usuario_id = %s AND m.nivel_rol IN (0,2,3)
                    AND NOT a.en_papelera""", [archivo_id, solicitante_id])
            fila = cursor.fetchone()
        if fila is None:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)
        checksum = self._checksums.pop(archivo_id, None) or fila[7]
        return ArchivoVerificado(fila[0], solicitante_id, *fila[1:7], checksum)

    def inspeccionar_objeto_tecnico(self, *, sesion_id, organizacion_id, clave):
        referenciado = Archivo.objects.using(self.using).filter(clave_s3=clave).exists()
        return InspeccionObjetoTecnico(sesion_id, organizacion_id, clave, referenciado, False)


def crear_servicios():
    """Construye el proveedor sin acceder a base de datos ni S3."""
    return validar_proveedor(ProveedorStorage())
