"""Composición opt-in: rutas propias antes del router general de metadatos."""

import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import include, path


def rutas_almacenamiento_y_negocio():
    """Los URLconf de negocio conservan su prefijo interno archivos/carpetas.

    No se importan apps de otra rama por su presencia en disco. El despliegue
    configura explícitamente los módulos después de resolver sus dependencias.
    """
    modulos = getattr(settings, "ALMACENAMIENTO_URLCONFS_NEGOCIO", ())
    if (not isinstance(modulos, (tuple, list))
            or any(not isinstance(modulo, str)
                   or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", modulo)
                   for modulo in modulos)
            or len(set(modulos)) != len(modulos)
            or "almacenamiento.urls" in modulos or "config.urls" in modulos):
        raise ImproperlyConfigured("URLconf de negocio inválido para almacenamiento")
    rutas = [path("api/v1/archivos/", include("almacenamiento.urls"))]
    for modulo in modulos:
        try:
            rutas.append(path("api/v1/", include(modulo)))
        except ImportError:
            raise ImproperlyConfigured("Falta un URLconf de negocio configurado") from None
    return rutas
