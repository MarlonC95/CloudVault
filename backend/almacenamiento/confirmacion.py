"""Fase 05: COPY como máximo una vez, hash final y commit de metadatos externos.

PREPARED es también el marcador durable de que COPY pudo haberse enviado. Un
reintento nunca vuelve a copiar, aunque HEAD todavía no encuentre el destino.
No hay borrado compensatorio del final ni modelos de negocio sustitutos.
"""

from contextlib import contextmanager
from dataclasses import asdict
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from auth_workspaces.models import LogAuditoria

from .contrato import CodigoError
from .errores import ErrorCarga
from .integracion import ArchivoVerificado
from .models import EstadoPublicacion, EstadoSesion, IntentoPublicacion, SesionCarga
from .persistencia import IntegridadCarga, RepositorioCargas
from .s3 import ContenidoS3, ErrorS3, ObjetoS3, _clave, nueva_clave_final
from .serializers import ArchivoIdSerializer, ConfirmarCargaInputSerializer
from .validacion import validar_checksum


MIME_PUBLICADO = "application/octet-stream"


def auditar_confirmacion(*, sesion, accion, using):
    LogAuditoria.objects.using(using).create(
        usuario_id=sesion.solicitante_id, organizacion_id=sesion.organizacion_id,
        accion=accion, detalles={"archivo_id": str(sesion.archivo_id),
                                 "sesion_id": str(sesion.id), "tamano_bytes": sesion.tamano_bytes})


class ServicioConfirmacionCargas:
    def __init__(self, *, servicios_factory, cliente_factory, verificador,
                 repositorio=None, maximo_bytes=1 << 30, auditoria=auditar_confirmacion):
        if type(maximo_bytes) is not int or not 0 < maximo_bytes <= 5 << 30:
            raise ValueError("Límite de publicación inválido")
        self.servicios_factory = servicios_factory
        self.cliente_factory = cliente_factory
        self.verificador = verificador
        self.repo = repositorio or RepositorioCargas()
        self.maximo_bytes = maximo_bytes
        self.auditoria = auditoria

    @contextmanager
    def _sql(self, servicios, sesion, comprobar):
        comprobar()
        with transaction.atomic(using=self.repo.using, durable=True):
            with self.repo.unidad_de_trabajo(organizacion_id=sesion.organizacion_id):
                with servicios.bloquear_cuota(organizacion_id=sesion.organizacion_id):
                    actual = self.repo._bloquear_sesion(
                        archivo_id=sesion.archivo_id, solicitante_id=sesion.solicitante_id)
                    inmutables = ("id", "archivo_id", "solicitante_id", "organizacion_id",
                                  "carpeta_id", "nombre", "tipo_mime", "tamano_bytes", "clave_temporal")
                    if any(getattr(actual, campo) != getattr(sesion, campo) for campo in inmutables):
                        raise IntegridadCarga("La reserva cambió durante la publicación")
                    yield actual

    def _destino(self, servicios, sesion):
        destino = servicios.resolver_destino(solicitante_id=sesion.solicitante_id,
                                             carpeta_id=sesion.carpeta_id)
        if destino.organizacion_id != sesion.organizacion_id:
            raise ErrorCarga(CodigoError.SIN_PERMISO)

    def _pendiente(self, sesion):
        if sesion.estado != EstadoSesion.PENDING or sesion.expira_en <= timezone.now():
            raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                             fields={"id": ["La sesión ya no admite confirmación."]})
        _clave(sesion.clave_temporal, propia=True)
        if "/temporales/" not in sesion.clave_temporal:
            raise IntegridadCarga("La sesión no tiene una clave temporal propia")
        if sesion.tamano_bytes > self.maximo_bytes:
            raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                             fields={"tamano_bytes": ["Supera el límite de publicación permitido."]})

    def _cuota(self, servicios, sesion):
        cuota = servicios.leer_cuota(organizacion_id=sesion.organizacion_id)
        pendientes = self.repo.bytes_pendientes(organizacion_id=sesion.organizacion_id)
        # R ya incluye S; no sumar otra vez la reserva propia.
        if cuota.usado_bytes + pendientes > cuota.limite_bytes:
            raise ErrorCarga(CodigoError.CUOTA_EXCEDIDA)
        return cuota

    def _intento(self, sesion):
        intento = IntentoPublicacion.objects.using(self.repo.using).select_for_update().filter(sesion=sesion).first()
        if intento is not None:
            if (intento.clave_final != nueva_clave_final(sesion.archivo_id)
                    or intento.estado not in (EstadoPublicacion.PREPARED, EstadoPublicacion.PUBLISHED)):
                raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                                 fields={"id": ["El intento ya no admite publicación."]})
        return intento

    def _repetir(self, servicios, sesion):
        intento = self._intento(sesion)
        if intento is None or intento.estado != EstadoPublicacion.PUBLISHED:
            raise IntegridadCarga("Confirmación sin ledger publicado")
        validar_checksum(sesion.checksum_sha256)
        if sesion.checksum_sha256 is None:
            raise IntegridadCarga("Confirmación sin hash final verificado")
        archivo = servicios.autorizar_descarga(solicitante_id=sesion.solicitante_id,
                                              archivo_id=sesion.archivo_id)
        if (archivo.organizacion_id != sesion.organizacion_id or archivo.clave_final != intento.clave_final
                or archivo.tamano_bytes != sesion.tamano_bytes
                or archivo.checksum_sha256 != sesion.checksum_sha256):
            raise IntegridadCarga("Metadatos confirmados incoherentes")
        return self.repo.confirmar_atomicamente(
            archivo_id=sesion.archivo_id, solicitante_id=sesion.solicitante_id,
            registrar_metadatos=lambda **kwargs: None)

    def _rechazar_contenido(self, servicios, sesion, comprobar):
        # Error después del commit intencional: no revertir la cancelación.
        with self._sql(servicios, sesion, comprobar) as actual:
            if actual.estado == EstadoSesion.PENDING:
                intento = self._intento(actual)
                if intento is not None:
                    self.repo.abandonar_publicacion(archivo_id=actual.archivo_id,
                                                   solicitante_id=actual.solicitante_id)
                self.repo.finalizar_sin_publicar(archivo_id=actual.archivo_id,
                                                solicitante_id=actual.solicitante_id,
                                                estado=EstadoSesion.CANCELED)
                self.auditoria(sesion=actual, accion="CARGA_RECHAZADA", using=self.repo.using)
        raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                         fields={"tamano_bytes": ["El contenido no coincide con el tamaño reservado."]})

    def confirmar(self, *, solicitante_id, archivo_id, datos):
        identificador = ArchivoIdSerializer(data={"id": archivo_id})
        identificador.is_valid(raise_exception=True)
        entrada = ConfirmarCargaInputSerializer(data=datos)
        entrada.is_valid(raise_exception=True)
        archivo_id = identificador.validated_data["id"]
        if not isinstance(solicitante_id, UUID):
            raise ErrorCarga(CodigoError.TOKEN_INVALIDO)
        servicios = self.servicios_factory()
        if servicios.using != self.repo.using:
            raise IntegridadCarga("Los alias SQL deben coincidir")
        if any(not callable(getattr(servicios.servicios, nombre, None))
               for nombre in ("registrar_archivo", "autorizar_descarga")):
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        try:
            sesion = self.repo.recuperar_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        except SesionCarga.DoesNotExist:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO) from None
        with self.repo.reclamar_publicador(archivo_id=archivo_id) as comprobar:
            with self._sql(servicios, sesion, comprobar) as actual:
                if actual.estado == EstadoSesion.CONFIRMED:
                    return self._repetir(servicios, actual)
                self._destino(servicios, actual)
                self._pendiente(actual)
                self._cuota(servicios, actual)
                intento = self._intento(actual)
                if (intento is not None and "etag" in entrada.validated_data
                        and entrada.validated_data["etag"] != intento.etag_origen):
                    raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                                     fields={"etag": ["No coincide con el intento reservado."]})
                sesion = actual
            cliente = self.cliente_factory()
            try:
                if intento is None:
                    origen = cliente.consultar(sesion.clave_temporal)
                    if origen.tamano_bytes != sesion.tamano_bytes:
                        self._rechazar_contenido(servicios, sesion, comprobar)
                    if ("etag" in entrada.validated_data
                            and entrada.validated_data["etag"] != origen.etag):
                        raise ErrorCarga(CodigoError.VALIDATION_ERROR,
                                         fields={"etag": ["No coincide con el objeto observado."]})
                    # No sobrescribir/adoptar un final sin ledger, ni siquiera propio.
                    clave_final = nueva_clave_final(archivo_id)
                    try:
                        cliente.consultar(clave_final)
                    except ErrorS3 as exc:
                        if exc.tipo != "ausente":
                            raise
                    else:
                        raise IntegridadCarga("Destino preexistente sin intento durable")
                    with self._sql(servicios, sesion, comprobar) as actual:
                        self._destino(servicios, actual)
                        self._pendiente(actual)
                        self._cuota(servicios, actual)
                        if self._intento(actual) is not None:
                            raise IntegridadCarga("Otro intento apareció durante la preparación")
                        intento = self.repo.preparar_publicacion(
                            archivo_id=archivo_id, solicitante_id=solicitante_id,
                            clave_final=clave_final, etag_origen=origen.etag,
                            version_origen=origen.version)
                    # PREPARED ya está confirmado; esta rama es el único emisor.
                    comprobar()
                    cliente.publicar_una_vez(sesion.clave_temporal, intento.clave_final,
                                             etag_origen=intento.etag_origen)
                # Recuperar PREPARED nunca llama COPY ni depende del temporal.
                try:
                    final = cliente.consultar(intento.clave_final)
                except ErrorS3 as exc:
                    if exc.tipo == "ausente":
                        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None
                    raise
                if not isinstance(final, ObjetoS3) or final.tipo_mime != MIME_PUBLICADO:
                    raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
                if final.tamano_bytes != sesion.tamano_bytes:
                    self._rechazar_contenido(servicios, sesion, comprobar)
                try:
                    contenido = self.verificador(clave=intento.clave_final,
                                                  tamano_bytes=sesion.tamano_bytes)
                except ErrorS3 as exc:
                    if exc.tipo == "contenido":
                        self._rechazar_contenido(servicios, sesion, comprobar)
                    raise
                if not isinstance(contenido, ContenidoS3) or contenido.tamano_bytes != sesion.tamano_bytes:
                    self._rechazar_contenido(servicios, sesion, comprobar)
                validar_checksum(contenido.sha256)
                if contenido.sha256 is None or cliente.consultar(intento.clave_final) != final:
                    raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
                with self._sql(servicios, sesion, comprobar) as actual:
                    self._destino(servicios, actual)
                    self._pendiente(actual)
                    cuota = self._cuota(servicios, actual)
                    self.repo.marcar_publicado(archivo_id=archivo_id, solicitante_id=solicitante_id,
                                               etag_final=final.etag, version_final=final.version)
                    archivo = ArchivoVerificado(
                        archivo_id, solicitante_id, actual.organizacion_id, actual.carpeta_id,
                        actual.nombre, intento.clave_final, actual.tamano_bytes,
                        MIME_PUBLICADO, contenido.sha256)
                    def registrar(**kwargs):
                        servicios.registrar_archivo(archivo=archivo)
                        registrado = servicios.autorizar_descarga(
                            solicitante_id=solicitante_id, archivo_id=archivo_id)
                        posterior = servicios.leer_cuota(organizacion_id=actual.organizacion_id)
                        if (asdict(registrado) != asdict(archivo)
                                or posterior.usado_bytes != cuota.usado_bytes + actual.tamano_bytes
                                or posterior.limite_bytes != cuota.limite_bytes
                                or posterior.periodo_fin != cuota.periodo_fin):
                            raise IntegridadCarga("Registro o autoridad de consumo incoherentes")
                        self.auditoria(sesion=actual, accion="CARGA_CONFIRMADA", using=self.repo.using)
                    resultado = self.repo.confirmar_atomicamente(
                        archivo_id=archivo_id, solicitante_id=solicitante_id,
                        registrar_metadatos=registrar, checksum_final=contenido.sha256)
                # Temporal recuperable desde CONFIRMED/PUBLISHED; limpieza fase 07.
                return resultado
            finally:
                cliente.cerrar()
