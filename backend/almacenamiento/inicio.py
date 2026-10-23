"""Fase 04: sesión y reserva antes de firmar; no sube objetos ni publica archivos."""

from datetime import timedelta
from math import floor
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from auth_workspaces.models import LogAuditoria

from .contrato import CodigoError, PoliticaCarga
from .errores import ErrorCarga
from .persistencia import IntegridadCarga, RepositorioCargas
from .s3 import FirmaS3, nueva_clave_temporal
from .serializers import IniciarCargaInputSerializer, IniciarCargaSuccessSerializer


def registrar_inicio(*, sesion, using):
    """Auditoría mínima en la misma conexión/commit; nunca guarda firma ni secretos."""
    LogAuditoria.objects.using(using).create(
        usuario_id=sesion.solicitante_id, organizacion_id=sesion.organizacion_id,
        accion="CARGA_INICIADA", detalles={"archivo_id": str(sesion.archivo_id),
                                          "sesion_id": str(sesion.id),
                                          "tamano_bytes": sesion.tamano_bytes},
    )


class ServicioInicioCargas:
    def __init__(self, *, servicios_factory, firmador_factory, repositorio=None,
                 politica=None, limite_inicios=10, ventana_segundos=60,
                 auditoria=registrar_inicio):
        self.servicios_factory = servicios_factory
        self.firmador_factory = firmador_factory
        self.repo = repositorio or RepositorioCargas()
        self.politica = politica or PoliticaCarga()
        self.limite_inicios = limite_inicios
        self.ventana_segundos = ventana_segundos
        self.auditoria = auditoria

    def iniciar(self, *, solicitante_id, datos):
        entrada = IniciarCargaInputSerializer(data=datos, context={"politica": self.politica})
        entrada.is_valid(raise_exception=True)
        if not isinstance(solicitante_id, UUID):
            raise ErrorCarga(CodigoError.TOKEN_INVALIDO)
        datos = entrada.validated_data
        servicios = self.servicios_factory()
        destino = servicios.resolver_destino(solicitante_id=solicitante_id,
                                             carpeta_id=datos["carpeta_id"])
        if servicios.using != self.repo.using:
            raise IntegridadCarga("Los alias SQL deben coincidir")
        firmador = self.firmador_factory()  # Cliente explícito; sin acceso remoto.
        try:
            # No devolver éxito desde una transacción exterior aún no confirmada.
            with transaction.atomic(using=self.repo.using, durable=True):
                with self.repo.limitar_inicios(solicitante_id=solicitante_id,
                                              limite=self.limite_inicios,
                                              ventana_segundos=self.ventana_segundos):
                    with self.repo.unidad_de_trabajo(organizacion_id=destino.organizacion_id):
                        with servicios.bloquear_cuota(organizacion_id=destino.organizacion_id):
                            actual = servicios.resolver_destino(solicitante_id=solicitante_id,
                                                                carpeta_id=datos["carpeta_id"])
                            if actual != destino:
                                raise ErrorCarga(CodigoError.SIN_PERMISO)
                            cuota = servicios.leer_cuota(organizacion_id=destino.organizacion_id)
                            ahora = timezone.now()
                            pendientes = self.repo.bytes_pendientes(
                                organizacion_id=destino.organizacion_id, ahora=ahora)
                            if cuota.usado_bytes + pendientes + datos["tamano_bytes"] > cuota.limite_bytes:
                                raise ErrorCarga(CodigoError.CUOTA_EXCEDIDA)
                            vigencia = min(self.politica.vigencia_carga_segundos,
                                           floor((cuota.periodo_fin - ahora).total_seconds()))
                            if vigencia < 1:
                                raise ErrorCarga(CodigoError.SIN_PERMISO)
                            # Solo expira reservas sin intento activo: nunca borra objetos.
                            self.repo.expirar_sin_publicacion(organizacion_id=destino.organizacion_id,
                                                             ahora=ahora)
                            clave = nueva_clave_temporal()
                            sesion = self.repo.crear_sesion(
                                archivo_id=uuid4(), destino=destino, **{k: datos[k] for k in (
                                    "nombre", "tipo_mime", "tamano_bytes")}, clave_temporal=clave,
                                expira_en=ahora + timedelta(seconds=vigencia), politica=self.politica,
                                creado_en=ahora)
                            # Solo cálculo local SigV4. Ningún PUT/GET/HEAD durante el bloqueo.
                            firma = firmador.firmar_put(clave, datos["tipo_mime"], vigencia=vigencia)
                            if (not isinstance(firma, FirmaS3) or firma.metodo != "PUT"
                                    or firma.encabezados != {"Content-Type": datos["tipo_mime"]}):
                                raise IntegridadCarga("Firma incompatible con el contrato")
                            if (timezone.is_naive(firma.expira_en) or firma.expira_en <= timezone.now()
                                    or firma.expira_en > cuota.periodo_fin):
                                raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
                            sesion.expira_en = firma.expira_en
                            sesion.save(using=self.repo.using, update_fields=["expira_en"])
                            salida = IniciarCargaSuccessSerializer(data={"data": {
                                "archivo_id": str(sesion.archivo_id), "url_subida": firma.url,
                                "metodo": firma.metodo, "encabezados": firma.encabezados,
                                "expira_en": firma.expira_en,
                            }})
                            if not salida.is_valid():
                                raise IntegridadCarga("Respuesta de firma inválida")
                            resultado = salida.data
                            self.auditoria(sesion=sesion, using=self.repo.using)
            return resultado  # La transacción durable ya confirmó.
        finally:
            firmador.cerrar()
