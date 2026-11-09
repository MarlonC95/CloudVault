"""Comprueba que los settings offline bloquean conexión y resolución externas."""

import socket

from django.test import SimpleTestCase


class GuardasOfflineTests(SimpleTestCase):
    def test_socket_y_dns_fallan_antes_de_intentar_red(self):
        cliente = socket.socket()
        try:
            with self.assertRaisesRegex(AssertionError, "suite offline"):
                cliente.connect(("203.0.113.1", 443))
            with self.assertRaisesRegex(AssertionError, "suite offline"):
                socket.create_connection(("example.invalid", 443))
            with self.assertRaisesRegex(AssertionError, "suite offline"):
                socket.getaddrinfo("example.invalid", 443)
        finally:
            cliente.close()
