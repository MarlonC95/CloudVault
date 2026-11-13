"""Pruebas aisladas de storage: sin .env, conexiones o creación de BD."""
import socket
from unittest.mock import patch

from almacenamiento.tests.settings import *  # noqa: F403

INSTALLED_APPS = list(dict.fromkeys([*INSTALLED_APPS, "storage", "subscriptions", "compartir"]))  # noqa: F405
ALMACENAMIENTO_URLCONFS_NEGOCIO = ["storage.urls", "subscriptions.urls", "compartir.urls"]


def _rechazar_red(*args, **kwargs):
    raise AssertionError("La suite offline intentó usar la red.")


# Guardas activas durante toda la suite: ni apertura de sockets ni resolución DNS.
_guardas_red = [
    patch.object(socket.socket, "connect", side_effect=_rechazar_red).start(),
    patch.object(socket.socket, "connect_ex", side_effect=_rechazar_red).start(),
    patch.object(socket, "create_connection", side_effect=_rechazar_red).start(),
    patch.object(socket, "getaddrinfo", side_effect=_rechazar_red).start(),
    patch.object(socket, "gethostbyname", side_effect=_rechazar_red).start(),
]
