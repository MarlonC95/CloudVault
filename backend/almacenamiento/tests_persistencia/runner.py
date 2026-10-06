import os
from pathlib import Path

from django.db import connection, connections
from django.test.runner import DiscoverRunner


class RunnerAislado(DiscoverRunner):
    def setup_databases(self, **kwargs):
        # El controlador instaló el SQL literal. Nunca crea, borra ni migra una
        # base externa. Verificar la propiedad del servidor antes de los tests.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, current_setting('data_directory')")
            base, usuario, datos = cursor.fetchone()
        esperado = Path(os.environ["CLOUDVAULT_FASE2_TMP"]) / "datos"
        if base != "test_cloudvault_fase2" or usuario != "cloudvault_pruebas" or Path(datos) != esperado:
            raise RuntimeError("Servidor ajeno al clúster desechable")
        return None

    def teardown_databases(self, old_config, **kwargs):
        connections.close_all()
