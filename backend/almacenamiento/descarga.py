"""Fase 06: permisos actuales, publicación durable, HEAD y firma GET local.

No implementa ACL/modelos/planes; no devuelve archivos a través de Django.
El límite durable cuenta emisiones aceptadas, no peticiones rechazadas.
"""

from contextlib import contextmanager
from datetime import timedelta
from hashlib import sha256
import logging
from uuid import UUID

from django.db import connections, transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled

from auth_workspaces.models import LogAuditoria

from .contrato import CodigoError
from .errores import ErrorCarga
from .models import EstadoPublicacion, EstadoSesion, IntentoPublicacion
from .persistencia import IntegridadCarga
from .s3 import ErrorS3, FirmaS3, ObjetoS3, disposicion_adjunto, nueva_clave_final
from .serializers import ArchivoIdSerializer, DescargaSuccessSerializer


ACCION_DESCARGA = "DESCARGA_AUTORIZADA"
logger = logging.getLogger(__name__)


def auditar_descarga(*, archivo, using):
    LogAuditoria.objects.using(using).create(
        usuario_id=archivo.solicitante_id, organizacion_id=archivo.organizacion_id,
        accion=ACCION_DESCARGA, detalles={"archivo_id": str(archivo.archivo_id)})


class ServicioDescargas:
    def __init__(self, *, servicios_factory, cliente_factory, vigencia=300,
                 limite=30, ventana_segundos=60, using="default", auditoria=auditar_descarga):
        if (type(vigencia) is not int or not 1 <= vigencia <= 300
                or any(type(v) is not int or v <= 0 for v in (limite, ventana_segundos))):
            raise ValueError("Política de descarga inválida")
        self.servicios_factory = servicios_factory
        self.cliente_factory = cliente_factory
        self.vigencia = vigencia
        self.limite = limite
        self.ventana_segundos = ventana_segundos
        self.using = using
        self.auditoria = auditoria

    def _publicacion(self, archivo):
        if archivo.clave_final != nueva_clave_final(archivo.archivo_id):
            raise IntegridadCarga("El archivo no tiene una clave final canónica")
        # Validar el nombre antes de SDK; no aceptar headers ni paths del cliente.
        disposicion_adjunto(archivo.nombre)
        intento = IntentoPublicacion.objects.using(self.using).select_related("sesion").filter(
            sesion__archivo_id=archivo.archivo_id).first()
        if intento is None or intento.sesion.estado != EstadoSesion.CONFIRMED:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)
        sesion = intento.sesion
        if (intento.estado != EstadoPublicacion.PUBLISHED or not intento.etag_final
                or intento.clave_final != archivo.clave_final
                or sesion.organizacion_id != archivo.organizacion_id
                or sesion.tamano_bytes != archivo.tamano_bytes
                or sesion.etag != intento.etag_final
                or not sesion.checksum_sha256 or sesion.checksum_sha256 != archivo.checksum_sha256):
            raise IntegridadCarga("Metadatos y publicación confirmada incoherentes")
        return intento.etag_final, intento.version_final

    @contextmanager
    def _limitar(self, actor):
        connection = connections[self.using]
        if connection.vendor != "postgresql" or not connection.in_atomic_block:
            raise RuntimeError("El límite de descargas requiere transacción PostgreSQL")
        llave = int.from_bytes(sha256(f"cloudvault:descargas:v1:actor:{actor}".encode()).digest()[:8],
                               "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            if cursor.fetchone()[0] != "read committed":
                raise RuntimeError("Descargas requieren READ COMMITTED")
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [llave])
        ahora = timezone.now()
        recientes = LogAuditoria.objects.using(self.using).filter(
            usuario_id=actor, accion=ACCION_DESCARGA,
            fecha_evento__gte=ahora-timedelta(seconds=self.ventana_segundos))
        if recientes.count() >= self.limite:
            primero = recientes.order_by("fecha_evento").first()
            espera = max(1, (primero.fecha_evento + timedelta(seconds=self.ventana_segundos)-ahora).total_seconds())
            raise Throttled(wait=espera)
        yield

    def descargar(self, *, solicitante_id, archivo_id):
        identificador = ArchivoIdSerializer(data={"id": archivo_id})
        identificador.is_valid(raise_exception=True)
        archivo_id = identificador.validated_data["id"]
        if not isinstance(solicitante_id, UUID):
            raise ErrorCarga(CodigoError.TOKEN_INVALIDO)
        servicios = self.servicios_factory()
        if servicios.using != self.using:
            raise IntegridadCarga("Los alias SQL deben coincidir")
        if not callable(getattr(servicios.servicios, "autorizar_descarga", None)):
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        if connections[self.using].in_atomic_block:
            raise RuntimeError("La descarga no admite transacción exterior")
        archivo = servicios.autorizar_descarga(solicitante_id=solicitante_id, archivo_id=archivo_id)
        evidencia = self._publicacion(archivo)
        cliente = self.cliente_factory()
        try:
            # HEAD fuera de transacciones: nunca transferir contenido bajo locks.
            try:
                objeto = cliente.consultar(archivo.clave_final)
            except ErrorS3 as exc:
                if exc.tipo == "ausente":
                    self._registrar_inconsistencia(archivo, "ausente")
                raise
            if (not isinstance(objeto, ObjetoS3) or objeto.tamano_bytes != archivo.tamano_bytes
                    or (objeto.etag, objeto.version) != evidencia):
                self._registrar_inconsistencia(archivo, "evidencia")
                raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
            with transaction.atomic(using=self.using, durable=True):
                with self._limitar(solicitante_id):
                    actual = servicios.autorizar_descarga(solicitante_id=solicitante_id, archivo_id=archivo_id)
                    if actual != archivo or self._publicacion(actual) != evidencia:
                        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
                    firma = cliente.firmar_descarga(actual.clave_final, actual.nombre,
                                                   vigencia=self.vigencia, version=evidencia[1])
                    if (not isinstance(firma, FirmaS3) or firma.metodo != "GET" or firma.encabezados
                            or timezone.is_naive(firma.expira_en) or firma.expira_en <= timezone.now()
                            or firma.expira_en > timezone.now() + timedelta(seconds=self.vigencia)):
                        raise IntegridadCarga("Firma de descarga incompatible")
                    salida = DescargaSuccessSerializer(data={"data": {
                        "url_descarga": firma.url, "nombre": actual.nombre, "expira_en": firma.expira_en}})
                    if not salida.is_valid():
                        raise IntegridadCarga("Respuesta de descarga inválida")
                    resultado = salida.data
                    self.auditoria(archivo=actual, using=self.using)
            return resultado  # Evento y límite durables antes de responder.
        finally:
            cliente.cerrar()

    @staticmethod
    def _registrar_inconsistencia(archivo, motivo):
        logger.warning("Descarga inconsistente (actor=%s, organización=%s, archivo=%s, motivo=%s)",
                       archivo.solicitante_id, archivo.organizacion_id, archivo.archivo_id, motivo)
