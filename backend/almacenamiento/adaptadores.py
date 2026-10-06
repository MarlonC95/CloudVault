"""Validación de la frontera con servicios de German, suministrados por el equipo.

No resuelve ACL, planes ni modelos de negocio por su cuenta. Un proveedor debe
declarar su alias SQL y participar en la misma transacción al registrar archivos.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from uuid import UUID

from django.db import connections
from django.utils import timezone

from .contrato import CLAVE_FINAL_MAXIMA, TAMANO_SQL_MAXIMO
from .integracion import ArchivoVerificado, CuotaVigente, DependenciasAlmacenamiento, DestinoAutorizado
from .persistencia import IntegridadCarga
from .serializers import NombreArchivo, TipoMime
from .validacion import validar_checksum, validar_texto_tecnico


class ServiciosCompartidosValidados:
    def __init__(self, servicios: DependenciasAlmacenamiento, *, using="default"):
        if getattr(servicios, "using", None) != using:
            raise IntegridadCarga("Los servicios deben usar la misma conexión SQL")
        self.servicios = servicios
        self.using = using
        self._cuota_bloqueada = ContextVar(f"cuota_validada_{id(self)}", default=None)

    def resolver_destino(self, *, solicitante_id: UUID, carpeta_id: UUID | None):
        if not isinstance(solicitante_id, UUID) or (carpeta_id is not None and not isinstance(carpeta_id, UUID)):
            raise IntegridadCarga("Identidades de destino inválidas")
        destino = self.servicios.resolver_destino(solicitante_id=solicitante_id, carpeta_id=carpeta_id)
        if (not isinstance(destino, DestinoAutorizado)
                or destino.solicitante_id != solicitante_id or destino.carpeta_id != carpeta_id
                or not isinstance(destino.organizacion_id, UUID)):
            raise IntegridadCarga("El servicio devolvió otro destino")
        return destino

    @contextmanager
    def bloquear_cuota(self, *, organizacion_id):
        if not isinstance(organizacion_id, UUID) or self._cuota_bloqueada.get() is not None:
            raise IntegridadCarga("Ámbito de bloqueo inválido")
        with self.servicios.bloquear_cuota(organizacion_id=organizacion_id):
            if not connections[self.using].in_atomic_block:
                raise RuntimeError("El bloqueo compartido debe mantener una transacción SQL")
            token = self._cuota_bloqueada.set(organizacion_id)
            try:
                yield
            finally:
                self._cuota_bloqueada.reset(token)

    def leer_cuota(self, *, organizacion_id):
        if not connections[self.using].in_atomic_block or self._cuota_bloqueada.get() != organizacion_id:
            raise RuntimeError("Leer cuota dentro del bloqueo y la transacción compartidos")
        cuota = self.servicios.leer_cuota(organizacion_id=organizacion_id)
        if (not isinstance(cuota, CuotaVigente) or cuota.organizacion_id != organizacion_id
                or type(cuota.limite_bytes) is not int or not 0 < cuota.limite_bytes <= TAMANO_SQL_MAXIMO
                or type(cuota.usado_bytes) is not int or not 0 <= cuota.usado_bytes <= TAMANO_SQL_MAXIMO):
            raise IntegridadCarga("Cuota incoherente")
        if (not isinstance(cuota.periodo_fin, datetime) or timezone.is_naive(cuota.periodo_fin)
                or cuota.periodo_fin <= timezone.now()):
            raise IntegridadCarga("Período de cuota no utilizable")
        return cuota

    def _validar_archivo(self, archivo):
        if not isinstance(archivo, ArchivoVerificado) or not all(
            isinstance(v, UUID) for v in (archivo.archivo_id, archivo.solicitante_id, archivo.organizacion_id)
        ) or (archivo.carpeta_id is not None and not isinstance(archivo.carpeta_id, UUID)):
            raise IntegridadCarga("Identidades de archivo incoherentes")
        NombreArchivo().run_validation(archivo.nombre)
        TipoMime().run_validation(archivo.tipo_mime)
        validar_texto_tecnico(archivo.clave_final, CLAVE_FINAL_MAXIMA, "Clave final")
        validar_checksum(archivo.checksum_sha256)
        if type(archivo.tamano_bytes) is not int or not 0 <= archivo.tamano_bytes <= TAMANO_SQL_MAXIMO:
            raise IntegridadCarga("Tamaño de archivo incoherente")

    def registrar_archivo(self, *, archivo):
        self._validar_archivo(archivo)
        if not connections[self.using].in_atomic_block:
            raise RuntimeError("Registrar metadatos dentro de la transacción de confirmación")
        self.servicios.registrar_archivo(archivo=archivo)

    def autorizar_descarga(self, *, solicitante_id, archivo_id):
        if not all(isinstance(valor, UUID) for valor in (solicitante_id, archivo_id)):
            raise IntegridadCarga("Identidades de descarga inválidas")
        archivo = self.servicios.autorizar_descarga(solicitante_id=solicitante_id, archivo_id=archivo_id)
        self._validar_archivo(archivo)
        if archivo.archivo_id != archivo_id or archivo.solicitante_id != solicitante_id:
            raise IntegridadCarga("El servicio devolvió otro archivo o actor")
        return archivo
