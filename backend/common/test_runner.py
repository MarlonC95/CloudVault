"""Runner de pruebas para el esquema propiedad del SQL desplegado.

Crea la BD de pruebas y carga ``database/schema_desplegado.sql``: el DDL reconstruido de
``public`` (tablas, restricciones, índices, triggers de cuota/marca de tiempo y planes).
Es la fuente de verdad: ``database/schema.sql`` del repositorio quedó desactualizado.
Exige ``DB_TEST_NAME`` distinto de la BD real.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner


def _leer(nombre):
    return (Path(settings.BASE_DIR).parent / "database" / nombre).read_text(encoding="utf-8")


class CloudVaultTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        db_settings = settings.DATABASES["default"]
        test_name = db_settings.get("TEST", {}).get("NAME")
        if not test_name or test_name == db_settings["NAME"]:
            raise ImproperlyConfigured("DB_TEST_NAME debe ser una base distinta de DB_NAME")
        old_config = super().setup_databases(**kwargs)
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute(_leer("schema_desplegado.sql"))
        except Exception:
            self.teardown_databases(old_config)
            raise
        return old_config
