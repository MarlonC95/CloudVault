"""Interfaces que consumirá Dani; no implementan modelos ni CRUD de German."""

from dataclasses import dataclass
from datetime import datetime
from typing import ContextManager, Protocol
from uuid import UUID


@dataclass(frozen=True)
class DestinoAutorizado:
    solicitante_id: UUID
    organizacion_id: UUID
    carpeta_id: UUID | None


@dataclass(frozen=True)
class CuotaVigente:
    organizacion_id: UUID
    limite_bytes: int
    usado_bytes: int
    periodo_fin: datetime


@dataclass(frozen=True)
class ArchivoVerificado:
    archivo_id: UUID
    solicitante_id: UUID
    organizacion_id: UUID
    carpeta_id: UUID | None
    nombre: str
    clave_final: str
    tamano_bytes: int
    tipo_mime: str
    checksum_sha256: str | None


class DependenciasAlmacenamiento(Protocol):
    """Contrato interno: cada método autoriza usando datos actuales, nunca el body."""

    using: str  # Alias SQL compartido con Dani; no se admite publicación remota.

    def resolver_destino(
        self, *, solicitante_id: UUID, carpeta_id: UUID | None
    ) -> DestinoAutorizado:
        """Carpeta autorizada o raíz de un único ámbito habilitado; ambigüedad: 400."""
        ...

    def bloquear_cuota(self, *, organizacion_id: UUID) -> ContextManager[None]:
        """Bloqueo estable compartido por los escritores, dentro de transacción SQL."""
        ...

    def leer_cuota(self, *, organizacion_id: UUID) -> CuotaVigente:
        """Leer bajo bloqueo; exige organización/plan activos y período utilizable."""
        ...

    def registrar_archivo(self, *, archivo: ArchivoVerificado) -> None:
        """Publicar UUID único con el modelo real dentro de la transacción final."""
        ...

    def autorizar_descarga(
        self, *, solicitante_id: UUID, archivo_id: UUID
    ) -> ArchivoVerificado:
        """Permiso vigente y archivo confirmado accesible; nunca clave del cliente."""
        ...
