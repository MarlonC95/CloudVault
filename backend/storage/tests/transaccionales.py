"""Base de integración para reclamos de sesión, sin transacción exterior de TestCase.

No ejecutar con la restricción vigente: requiere una BD de pruebas explícita.
Las tablas unmanaged no participan en flush: retiramos las fixtures creadas por
cada test, preservando las filas iniciales (incluidos los planes del seed).
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections, transaction
from rest_framework.test import APITransactionTestCase

from auth_workspaces.models import Usuario
from subscriptions.models import Organizacion


class StorageTransactionTestCase(APITransactionTestCase):
    @classmethod
    def _fixture_setup(cls):
        config = connections['default'].settings_dict
        test_name = settings.DATABASES['default'].get('TEST', {}).get('NAME')
        if not test_name or config['NAME'] != test_name:
            raise ImproperlyConfigured('Storage requiere DB_TEST_NAME y el runner de pruebas.')
        super()._fixture_setup()
        cls._organizaciones_iniciales = list(Organizacion.objects.values_list('pk', flat=True))
        cls._usuarios_iniciales = list(Usuario.objects.values_list('pk', flat=True))

    def _fixture_teardown(self):
        try:
            with transaction.atomic():
                Organizacion.objects.exclude(pk__in=self._organizaciones_iniciales).delete()
                Usuario.objects.exclude(pk__in=self._usuarios_iniciales).delete()
        finally:
            super()._fixture_teardown()
