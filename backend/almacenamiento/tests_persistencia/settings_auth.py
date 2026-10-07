"""Regresión de auth privada con política existente y mapping observado.

No cambia settings de producción ni usa su conexión DB. La variante de fecha
se instala únicamente en el clúster propio, separada del SQL literal de storage.
"""

from almacenamiento.tests_persistencia.settings import *  # noqa: F403
from config.settings import AUTH_PASSWORD_VALIDATORS, REST_FRAMEWORK, SIMPLE_JWT, TEMPLATES  # noqa: F401
