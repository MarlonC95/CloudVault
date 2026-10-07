"""Runner de pruebas para el esquema propiedad del SQL (``database/``).

Crea la BD de pruebas con las extensiones ya presentes y carga, en orden:
función de marca de tiempo -> schema.sql -> triggers.sql -> seeds.sql.
Exige ``DB_TEST_NAME`` distinto de la BD real (como el runner de ``config``).
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner

MARCADOR_TRIGGERS = "DROP TRIGGER IF EXISTS"
# schema.sql concede permisos al rol de solo lectura que ``roles.sql`` crea a nivel de clúster.
CREAR_ROL_LECTOR = """DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lector_cloudvault') THEN
        CREATE ROLE lector_cloudvault NOLOGIN;
    END IF;
END $$;"""

# DISCREPANCIA CONOCIDA (solo pruebas): auth_workspaces.Usuario mapea date_joined a la columna
# ``fecha_creacion`` pero database/schema.sql define ``usuarios.creado_en``. Hasta confirmar cuál
# es la correcta en la base desplegada, la BD de pruebas añade la columna para que el JWT pueda
# cargar al usuario. No modifica database/ ni el módulo de auth.
COMPAT_USUARIOS = """ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;"""


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
            triggers = _leer("triggers.sql")
            funcion_base = triggers.split(MARCADOR_TRIGGERS, 1)[0]
            with connections["default"].cursor() as cursor:
                cursor.execute(CREAR_ROL_LECTOR)
                cursor.execute(funcion_base)
                cursor.execute(_leer("schema.sql"))
                cursor.execute(triggers)
                cursor.execute(_leer("seeds.sql"))
                cursor.execute(COMPAT_USUARIOS)
        except Exception:
            self.teardown_databases(old_config)
            raise
        return old_config
