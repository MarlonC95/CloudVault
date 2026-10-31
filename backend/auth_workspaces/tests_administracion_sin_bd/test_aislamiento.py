"""Intentos sintéticos interceptados antes de abrir red o conectar una BD."""

import socket

from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import SimpleTestCase

from .runner import bloquear_accesos_reales


class AislamientoAdministracionTests(SimpleTestCase):
    def test_dns_y_conexion_estan_bloqueados_en_la_seleccion(self):
        for llamada, argumentos in (
            (socket.getaddrinfo, ("offline.example.test", 443)),
            (socket.gethostbyname, ("offline.example.test",)),
            (socket.create_connection, (("offline.example.test", 443),)),
        ):
            with self.subTest(api=llamada), self.assertRaisesRegex(AssertionError, "red"):
                llamada(*argumentos)
        with socket.socket() as conexion:
            for llamada, argumentos in (
                (conexion.connect, (("127.0.0.1", 1),)),
                (conexion.connect_ex, (("127.0.0.1", 1),)),
                (conexion.sendto, (b"synthetic", ("127.0.0.1", 1))),
            ):
                with self.subTest(api=llamada), self.assertRaisesRegex(AssertionError, "red"):
                    llamada(*argumentos)

    def test_conexion_bd_directa_al_wrapper_tambien_esta_bloqueada(self):
        # Unbound call: no backend, credenciales o instancia de conexión real.
        with self.assertRaisesRegex(AssertionError, "conectar a una BD"):
            BaseDatabaseWrapper.connect(None)

    def test_contexto_restaura_parches_al_terminar(self):
        dns_anterior = socket.getaddrinfo
        bd_anterior = BaseDatabaseWrapper.connect
        with bloquear_accesos_reales():
            self.assertIsNot(socket.getaddrinfo, dns_anterior)
            with self.assertRaisesRegex(AssertionError, "red"):
                socket.getaddrinfo("offline.example.test", 443)
        self.assertIs(socket.getaddrinfo, dns_anterior)
        self.assertIs(BaseDatabaseWrapper.connect, bd_anterior)

    def test_contexto_restaura_parches_si_la_ejecucion_falla(self):
        dns_anterior = socket.getaddrinfo
        bd_anterior = BaseDatabaseWrapper.connect
        with self.assertRaisesRegex(RuntimeError, "fallo sintético"):
            with bloquear_accesos_reales():
                raise RuntimeError("fallo sintético")
        self.assertIs(socket.getaddrinfo, dns_anterior)
        self.assertIs(BaseDatabaseWrapper.connect, bd_anterior)
