"""Interfaz pública del PDF; no registra endpoints ni accede a persistencia."""

from dataclasses import dataclass
from enum import StrEnum


NOMBRE_MAXIMO = 255
MIME_MAXIMO = 100
ETAG_MAXIMO = 255
TAMANO_SQL_MAXIMO = (1 << 63) - 1
# Capacidades del SQL técnico; los modelos deben reflejar el esquema literal.
CLAVE_TEMPORAL_SQL_MAXIMA = 1024
CLAVE_LEDGER_SQL_MAXIMA = 1024
# Una publicación también debe caber en archivos.clave_s3, que admite 255.
CLAVE_FINAL_MAXIMA = 255
# Referencia del SQL, no una autorización: los permisos efectivos los da German.
ROLES_CON_CAPACIDAD_DE_CARGA = frozenset({0, 2, 3})
UUID_PATRON = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
MIME_PATRON = r"^[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+(?![\s\S])"
NOMBRE_PATRON = r"^(?!\s*$)(?!\s*\.{1,2}\s*$)[^/\\\x00-\x1f\x7f]+$"


class CodigoError(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NO_AUTENTICADO = "NO_AUTENTICADO"
    TOKEN_INVALIDO = "TOKEN_INVALIDO"
    SIN_PERMISO = "SIN_PERMISO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    CUOTA_EXCEDIDA = "CUOTA_EXCEDIDA"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR_INTERNO = "ERROR_INTERNO"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


ESTADOS_HTTP_ERROR = {
    CodigoError.VALIDATION_ERROR: 400,
    CodigoError.NO_AUTENTICADO: 401,
    CodigoError.TOKEN_INVALIDO: 401,
    CodigoError.SIN_PERMISO: 403,
    CodigoError.NO_ENCONTRADO: 404,
    CodigoError.CUOTA_EXCEDIDA: 409,
    CodigoError.RATE_LIMITED: 429,
    CodigoError.ERROR_INTERNO: 500,
    CodigoError.SERVICE_UNAVAILABLE: 503,
}


@dataclass(frozen=True)
class Operacion:
    nombre: str
    metodo: str
    ruta: str
    estado_exito: int


INICIAR_CARGA = Operacion(
    "iniciar_carga", "POST", "/api/v1/archivos/iniciar-carga/", 201
)
CONFIRMAR_CARGA = Operacion(
    "confirmar_carga", "POST", "/api/v1/archivos/{id}/confirmar-carga/", 200
)
DESCARGA = Operacion(
    "descarga", "GET", "/api/v1/archivos/{id}/descarga/", 200
)
OPERACIONES = (INICIAR_CARGA, CONFIRMAR_CARGA, DESCARGA)


@dataclass(frozen=True)
class PoliticaCarga:
    """Valores locales de diseño; no cambian campos del contrato PDF."""

    maximo_archivo_bytes: int = 1 << 30
    vigencia_carga_segundos: int = 900
    vigencia_descarga_segundos: int = 300

    def __post_init__(self):
        limites = (
            ("maximo_archivo_bytes", self.maximo_archivo_bytes, TAMANO_SQL_MAXIMO),
            ("vigencia_carga_segundos", self.vigencia_carga_segundos, 900),
            ("vigencia_descarga_segundos", self.vigencia_descarga_segundos, 300),
        )
        for nombre, valor, maximo in limites:
            if type(valor) is not int or not 0 < valor <= maximo:
                raise ValueError(f"{nombre} debe ser un entero entre 1 y {maximo}.")
