"""Pruebas de ``subscriptions.espacio.asegurar_espacio_personal``."""

from django.test import TestCase

from auth_workspaces.models import Usuario
from common.testing import crear_organizacion, crear_suscripcion
from subscriptions.espacio import asegurar_espacio_personal
from subscriptions.models import MiembroOrganizacion, Organizacion, Suscripcion


class EspacioPersonalTests(TestCase):
    def test_crea_espacio_para_usuario_sin_membresia(self):
        usuario = Usuario.objects.create_user(
            correo_electronico="legado@example.test",
            password="UnaFraseSeguraPara2026",
            nombre_completo="Usuario Legado",
        )
        self.assertEqual(MiembroOrganizacion.objects.filter(usuario_id=usuario.id).count(), 0)

        organizacion_id = asegurar_espacio_personal(usuario.id)

        self.assertIsNotNone(organizacion_id)
        self.assertEqual(Organizacion.objects.filter(id=organizacion_id).count(), 1)
        self.assertEqual(
            MiembroOrganizacion.objects.filter(
                usuario_id=usuario.id, organizacion_id=organizacion_id, nivel_rol=0
            ).count(),
            1,
        )
        self.assertEqual(Suscripcion.objects.filter(organizacion_id=organizacion_id).count(), 1)

    def test_es_idempotente(self):
        usuario = Usuario.objects.create_user(
            correo_electronico="repetido@example.test",
            password="UnaFraseSeguraPara2026",
            nombre_completo="Usuario Repetido",
        )
        primera = asegurar_espacio_personal(usuario.id)
        segunda = asegurar_espacio_personal(usuario.id)
        self.assertEqual(primera, segunda)
        self.assertEqual(Organizacion.objects.count(), 1)
