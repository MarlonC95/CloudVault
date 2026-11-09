"""Runner exclusivo de administración; accesos reales fallan antes de ejecutarse."""

from contextlib import ExitStack, contextmanager
import socket
from unittest.mock import patch

from django.db.backends.base.base import BaseDatabaseWrapper
from django.test.runner import DiscoverRunner


def _rechazar_red(*args, **kwargs):
    raise AssertionError("La selección offline intentó acceder a la red.")


def _rechazar_bd(*args, **kwargs):
    raise AssertionError("La selección offline intentó conectar a una BD.")


@contextmanager
def bloquear_accesos_reales():
    """Protege descubrimiento, checks y tests; restaura parches incluso ante error.

    Complementa DATABASES={} y SimpleTestCase. Es una barrera de regresión para
    las APIs inspeccionadas, no un aislamiento del sistema operativo.
    """
    with ExitStack() as guardas:
        for nombre in (
            "create_connection", "getaddrinfo", "gethostbyname",
            "gethostbyname_ex", "gethostbyaddr",
        ):
            guardas.enter_context(patch.object(socket, nombre, side_effect=_rechazar_red))
        for nombre in ("connect", "connect_ex", "send", "sendall", "sendto", "sendmsg"):
            if hasattr(socket.socket, nombre):
                guardas.enter_context(patch.object(
                    socket.socket, nombre, side_effect=_rechazar_red,
                ))
        for nombre in ("connect", "ensure_connection"):
            guardas.enter_context(patch.object(
                BaseDatabaseWrapper, nombre, side_effect=_rechazar_bd,
            ))
        yield


class RunnerAdministracionSinBD(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        with bloquear_accesos_reales():
            return super().run_tests(test_labels, **kwargs)
