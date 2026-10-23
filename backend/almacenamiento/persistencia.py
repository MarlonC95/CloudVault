"""Primitivas SQL del flujo técnico; no firman URLs ni admiten cargas por HTTP.

No ajustan el contador de organizaciones ni crean metadatos de negocio. Las
operaciones de escritura exigen la unidad de trabajo de una organización.
Orden único: bloqueo de cuota -> sesión -> intento -> servicio de metadatos.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID

from django.db import connections, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import Throttled

from .contrato import CLAVE_FINAL_MAXIMA, CLAVE_TEMPORAL_SQL_MAXIMA
from .contrato import CodigoError
from .errores import ErrorCarga
from .integracion import DestinoAutorizado
from .models import EstadoPublicacion, EstadoSesion, IntentoPublicacion, SesionCarga
from .serializers import (
    ConfirmarCargaSuccessSerializer,
    IniciarCargaInputSerializer,
)
from .validacion import validar_checksum, validar_texto_tecnico


class EstadoIncompatible(ValueError):
    """Reintento contradictorio o transición no permitida; nunca éxito ficticio."""


class IntegridadCarga(ValueError):
    """Los datos durables no permiten continuar con seguridad."""


def clave_bloqueo_cuota(organizacion_id: UUID) -> int:
    if not isinstance(organizacion_id, UUID):
        raise TypeError("La organización debe ser un UUID")
    digest = sha256(f"cloudvault:cuota:v1:organizacion:{organizacion_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class RepositorioCargas:
    def __init__(self, *, using="default"):
        self.using = using
        self._ambito = ContextVar(f"ambito_carga_{id(self)}", default=None)

    @contextmanager
    def reclamar_publicador(self, *, archivo_id):
        """Un publicador por archivo sin mantener una transacción durante S3.

        Requiere conexión PostgreSQL directa o pool de sesiones, nunca pool de
        transacciones. Recuperar PREPARED solo inspecciona; no vuelve a copiar,
        incluso si se pierde la conexión y su advisory lock.
        """
        connection = connections[self.using]
        if not isinstance(archivo_id, UUID) or connection.in_atomic_block:
            raise RuntimeError("Reclamar fuera de una transacción, con UUID")
        if connection.vendor != "postgresql":
            raise RuntimeError("La publicación requiere PostgreSQL")
        connection.ensure_connection()
        original = connection.connection
        llave = int.from_bytes(sha256(f"cloudvault:publicador:v1:{archivo_id}".encode()).digest()[:8],
                               "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [llave])
            if not cursor.fetchone()[0]:
                raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        try:
            def comprobar():
                if connection.connection is not original or original.closed:
                    raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
            yield comprobar
        finally:
            if connection.connection is original and not original.closed:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_advisory_unlock(%s)", [llave])
                        if not cursor.fetchone()[0]:
                            connection.close()
                except Exception:
                    # No devolver una conexión con un lock retenido al pool.
                    connection.close()

    @contextmanager
    def limitar_inicios(self, *, solicitante_id, limite, ventana_segundos):
        """Limita inicios aceptados globalmente por actor; no cuenta peticiones fallidas.

        Orden: actor -> cuota -> sesión. Usa sesiones durables, sin caché local ni
        nuevas tablas. El bloqueo dura hasta commit/rollback exterior.
        """
        if (not isinstance(solicitante_id, UUID) or type(limite) is not int or limite <= 0
                or type(ventana_segundos) is not int or ventana_segundos <= 0):
            raise ValueError("Límite de inicios inválido")
        connection = connections[self.using]
        if connection.vendor != "postgresql" or not connection.in_atomic_block:
            raise RuntimeError("El límite requiere una transacción PostgreSQL")
        digest = sha256(f"cloudvault:inicios:v1:actor:{solicitante_id}".encode()).digest()
        llave = int.from_bytes(digest[:8], "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [llave])
        ahora = timezone.now()
        recientes = SesionCarga.objects.using(self.using).filter(
            solicitante_id=solicitante_id,
            creado_en__gte=ahora - timedelta(seconds=ventana_segundos),
        )
        if recientes.count() >= limite:
            primera = recientes.order_by("creado_en").first()
            espera = max(1, (primera.creado_en + timedelta(seconds=ventana_segundos) - ahora).total_seconds())
            raise Throttled(wait=espera)
        yield

    def expirar_sin_publicacion(self, *, organizacion_id, ahora):
        self._exigir_ambito(organizacion_id)
        return SesionCarga.objects.using(self.using).filter(
            organizacion_id=organizacion_id, estado=EstadoSesion.PENDING,
            expira_en__lte=ahora, intentopublicacion__isnull=True,
        ).update(estado=EstadoSesion.EXPIRED)

    @contextmanager
    def unidad_de_trabajo(self, *, organizacion_id: UUID):
        """Bloqueo PostgreSQL hasta commit/rollback; no usar durante I/O de S3."""
        if self._ambito.get() is not None:
            raise RuntimeError("No anidar unidades de trabajo ni cambiar de organización")
        connection = connections[self.using]
        if connection.vendor != "postgresql":
            raise RuntimeError("Se requiere PostgreSQL")
        with transaction.atomic(using=self.using):
            with connection.cursor() as cursor:
                cursor.execute("SHOW transaction_isolation")
                if cursor.fetchone()[0] != "read committed":
                    raise RuntimeError("La unidad de trabajo requiere READ COMMITTED")
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [clave_bloqueo_cuota(organizacion_id)])
            token = self._ambito.set(organizacion_id)
            try:
                yield
            finally:
                self._ambito.reset(token)

    def _exigir_ambito(self, organizacion_id):
        if not isinstance(organizacion_id, UUID) or self._ambito.get() != organizacion_id or not connections[self.using].in_atomic_block:
            raise RuntimeError("Operación fuera de la unidad de trabajo autorizada")

    def crear_sesion(self, *, archivo_id: UUID, destino: DestinoAutorizado,
                     nombre: str, tipo_mime: str, tamano_bytes: int,
                     clave_temporal: str, expira_en: datetime, politica=None,
                     creado_en=None) -> SesionCarga:
        """Persistir una sesión autorizada. La admisión de cuota corresponde a fase 04."""
        self._exigir_ambito(destino.organizacion_id)
        if not all(isinstance(v, UUID) for v in (archivo_id, destino.solicitante_id, destino.organizacion_id)):
            raise ValueError("Identidades inválidas")
        validador = IniciarCargaInputSerializer(data={
            "nombre": nombre, "tipo_mime": tipo_mime, "tamano_bytes": tamano_bytes,
            "carpeta_id": str(destino.carpeta_id) if destino.carpeta_id is not None else None,
        }, context={"politica": politica} if politica else {})
        validador.is_valid(raise_exception=True)
        if not isinstance(expira_en, datetime) or timezone.is_naive(expira_en) or expira_en <= timezone.now():
            raise ValueError("La expiración debe ser futura y tener zona horaria")
        validar_texto_tecnico(clave_temporal, CLAVE_TEMPORAL_SQL_MAXIMA, "Clave temporal")
        fechas = {}
        if creado_en is not None:
            if (not isinstance(creado_en, datetime) or timezone.is_naive(creado_en)
                    or creado_en >= expira_en):
                raise ValueError("Creación incompatible con expiración")
            fechas["creado_en"] = creado_en
        datos = validador.validated_data
        return SesionCarga.objects.using(self.using).create(
            archivo_id=archivo_id, solicitante_id=destino.solicitante_id,
            organizacion_id=destino.organizacion_id, carpeta_id=datos["carpeta_id"],
            nombre=datos["nombre"], tipo_mime=datos["tipo_mime"],
            tamano_bytes=datos["tamano_bytes"], clave_temporal=clave_temporal, expira_en=expira_en,
            **fechas,
        )

    def recuperar_sesion(self, *, archivo_id: UUID, solicitante_id: UUID) -> SesionCarga:
        """Filtrar por actor antes de devolver estado; no basta conocer el UUID."""
        return SesionCarga.objects.using(self.using).get(
            archivo_id=archivo_id, solicitante_id=solicitante_id
        )

    def _bloquear_sesion(self, *, archivo_id, solicitante_id):
        organizacion_id = self._ambito.get()
        self._exigir_ambito(organizacion_id)
        return SesionCarga.objects.using(self.using).select_for_update().get(
            archivo_id=archivo_id, solicitante_id=solicitante_id, organizacion_id=organizacion_id
        )

    def bytes_pendientes(self, *, organizacion_id: UUID, ahora=None) -> int:
        self._exigir_ambito(organizacion_id)
        return SesionCarga.objects.using(self.using).filter(
            organizacion_id=organizacion_id, estado=EstadoSesion.PENDING,
            expira_en__gt=timezone.now() if ahora is None else ahora,
        ).aggregate(total=Sum("tamano_bytes"))["total"] or 0

    def preparar_publicacion(self, *, archivo_id, solicitante_id, clave_final,
                            etag_origen, version_origen=None, checksum_origen=None):
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        if sesion.estado != EstadoSesion.PENDING or sesion.expira_en <= timezone.now():
            raise EstadoIncompatible("La sesión no admite publicación")
        validar_texto_tecnico(clave_final, CLAVE_FINAL_MAXIMA, "Clave final")
        validar_texto_tecnico(etag_origen, 255, "ETag origen")
        if version_origen is not None:
            validar_texto_tecnico(version_origen, 255, "Versión origen")
        validar_checksum(checksum_origen)
        datos = dict(clave_final=clave_final, etag_origen=etag_origen,
                     version_origen=version_origen, checksum_origen=checksum_origen)
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().filter(sesion=sesion).first()
        if intento is not None:
            if intento.estado not in (EstadoPublicacion.PREPARED, EstadoPublicacion.PUBLISHED) or any(
                getattr(intento, campo) != valor for campo, valor in datos.items()
            ):
                raise EstadoIncompatible("El intento existente tiene otro contenido o estado")
            return intento
        return IntentoPublicacion.objects.using(self.using).create(sesion=sesion, **datos)

    def marcar_publicado(self, *, archivo_id, solicitante_id, etag_final, version_final=None):
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        if sesion.estado != EstadoSesion.PENDING:
            raise EstadoIncompatible("La sesión no está pendiente")
        validar_texto_tecnico(etag_final, 255, "ETag final")
        if version_final is not None:
            validar_texto_tecnico(version_final, 255, "Versión final")
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().get(sesion=sesion)
        if intento.estado == EstadoPublicacion.PUBLISHED:
            if (intento.etag_final, intento.version_final) != (etag_final, version_final):
                raise EstadoIncompatible("El resultado publicado es distinto")
            return intento
        if intento.estado != EstadoPublicacion.PREPARED:
            raise EstadoIncompatible("El intento no admite publicación")
        intento.estado = EstadoPublicacion.PUBLISHED
        intento.etag_final, intento.version_final = etag_final, version_final
        intento.save(using=self.using, update_fields=["estado", "etag_final", "version_final"])
        return intento

    def finalizar_sin_publicar(self, *, archivo_id, solicitante_id, estado):
        if estado not in (EstadoSesion.CANCELED, EstadoSesion.EXPIRED):
            raise EstadoIncompatible("Transición no permitida")
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        if sesion.estado == estado:
            return sesion
        if sesion.estado != EstadoSesion.PENDING:
            raise EstadoIncompatible("La sesión ya tiene otro estado terminal")
        if estado == EstadoSesion.EXPIRED and sesion.expira_en > timezone.now():
            raise EstadoIncompatible("La sesión todavía no ha vencido")
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().filter(sesion=sesion).first()
        if intento is not None and intento.estado in (EstadoPublicacion.PREPARED, EstadoPublicacion.PUBLISHED):
            raise EstadoIncompatible("Reconciliar el intento antes de liberar la sesión")
        sesion.estado = estado
        sesion.save(using=self.using, update_fields=["estado"])
        return sesion

    def abandonar_publicacion(self, *, archivo_id, solicitante_id):
        """Marcar para reconciliar/limpiar; no afirma que S3 ya fue eliminado."""
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        if sesion.estado == EstadoSesion.CONFIRMED:
            raise EstadoIncompatible("No abandonar un archivo confirmado")
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().get(sesion=sesion)
        if intento.estado == EstadoPublicacion.CLEANED:
            return intento
        intento.estado = EstadoPublicacion.ABANDONED
        intento.save(using=self.using, update_fields=["estado"])
        return intento

    def marcar_limpiado(self, *, archivo_id, solicitante_id):
        """Solo después de verificar la eliminación de S3 en la fase 07."""
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().get(sesion=sesion)
        if sesion.estado == EstadoSesion.CONFIRMED or intento.estado not in (
            EstadoPublicacion.ABANDONED, EstadoPublicacion.CLEANED
        ):
            raise EstadoIncompatible("El intento no admite limpieza")
        if intento.estado != EstadoPublicacion.CLEANED:
            intento.estado = EstadoPublicacion.CLEANED
            intento.save(using=self.using, update_fields=["estado"])
        return intento

    def confirmar_atomicamente(self, *, archivo_id, solicitante_id, registrar_metadatos,
                               checksum_final=None):
        """Callback de German en ESTA conexión; sin llamadas S3 dentro del lock.

        El coordinador de fase 05 revalida permisos/destino, cuota y contenido.
        El callback es servicio confiable del servidor, nunca un dato del cliente.
        """
        sesion = self._bloquear_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        if sesion.estado == EstadoSesion.CONFIRMED:
            if sesion.resultado_confirmacion is None:
                raise IntegridadCarga("Confirmación sin resultado durable")
            respuesta = ConfirmarCargaSuccessSerializer(data=sesion.resultado_confirmacion)
            respuesta.is_valid(raise_exception=True)
            datos = respuesta.validated_data["data"]
            if (datos["id"] != sesion.archivo_id or datos["nombre"] != sesion.nombre
                    or datos["es_nuevo"] is not True or datos["en_papelera"] is not False):
                raise IntegridadCarga("Resultado incoherente con la sesión")
            return sesion.resultado_confirmacion
        if sesion.estado != EstadoSesion.PENDING or sesion.expira_en <= timezone.now():
            raise EstadoIncompatible("La sesión no admite confirmación")
        intento = IntentoPublicacion.objects.using(self.using).select_for_update().get(sesion=sesion)
        if intento.estado != EstadoPublicacion.PUBLISHED or not intento.etag_final:
            raise EstadoIncompatible("Publicación todavía no verificada")
        validar_checksum(checksum_final)
        # El savepoint revierte metadatos y sesión incluso si el llamador captura
        # el error y decide confirmar la transacción exterior.
        with transaction.atomic(using=self.using):
            registrar_metadatos(sesion=sesion, intento=intento, using=self.using)
            resultado = {"data": {"id": str(sesion.archivo_id), "nombre": sesion.nombre,
                                  "es_nuevo": True, "en_papelera": False}}
            sesion.estado = EstadoSesion.CONFIRMED
            sesion.resultado_confirmacion = resultado
            sesion.etag = intento.etag_final
            sesion.checksum_sha256 = (checksum_final if checksum_final is not None else intento.checksum_origen)
            sesion.save(using=self.using, update_fields=["estado", "resultado_confirmacion", "etag", "checksum_sha256"])
        return resultado
