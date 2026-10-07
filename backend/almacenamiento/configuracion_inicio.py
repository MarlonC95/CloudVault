"""Configuración propia; sin defaults de cuota ni servicios ficticios en runtime."""

import os

from django.conf import settings
from django.utils.module_loading import import_string

from .adaptadores import ServiciosCompartidosValidados
from .configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida
from .contrato import CodigoError, PoliticaCarga
from .errores import ErrorCarga
from .s3 import ClienteS3


def entero_configurado(nombre, defecto):
    valor = getattr(settings, nombre, os.environ.get(nombre, defecto))
    if type(valor) is int:
        numero = valor
    elif isinstance(valor, str) and valor.isascii() and valor.isdecimal():
        numero = int(valor)
    else:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    if numero <= 0:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    return numero


def politica_inicio():
    try:
        return PoliticaCarga(
            maximo_archivo_bytes=entero_configurado("ALMACENAMIENTO_MAXIMO_ARCHIVO_BYTES", 1 << 30),
            vigencia_carga_segundos=entero_configurado("ALMACENAMIENTO_VIGENCIA_CARGA_SEGUNDOS", 900),
        )
    except ValueError:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None


def servicios_compartidos():
    fabrica = getattr(settings, "ALMACENAMIENTO_SERVICIOS_FACTORY",
                       os.environ.get("ALMACENAMIENTO_SERVICIOS_FACTORY", ""))
    if not fabrica:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    try:
        proveedor = import_string(fabrica)() if isinstance(fabrica, str) else fabrica()
        return ServiciosCompartidosValidados(proveedor)
    except (ImportError, TypeError, ValueError, AttributeError):
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None


def cliente_firmador():
    try:
        return ClienteS3(ConfiguracionS3.desde_entorno())
    except ConfiguracionS3Invalida:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None


def maximo_publicacion():
    maximo = entero_configurado("ALMACENAMIENTO_MAXIMO_PUBLICACION_BYTES",
                               min(politica_inicio().maximo_archivo_bytes, 5 << 30))
    if maximo > 5 << 30:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    return maximo


def verificador_publicacion():
    from .verificacion import VerificadorSubproceso

    tiempo = entero_configurado("ALMACENAMIENTO_VERIFICACION_SEGUNDOS", 60)
    if tiempo > 300:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    return VerificadorSubproceso(tiempo_maximo=tiempo)
