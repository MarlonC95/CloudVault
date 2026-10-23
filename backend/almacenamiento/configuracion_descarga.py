"""Política propia de descarga, sin editar .env ni configuración compartida."""

from .configuracion_inicio import entero_configurado
from .contrato import CodigoError
from .errores import ErrorCarga


def vigencia_descarga():
    vigencia = entero_configurado("ALMACENAMIENTO_VIGENCIA_DESCARGA_SEGUNDOS", 300)
    if vigencia > 300:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    return vigencia
