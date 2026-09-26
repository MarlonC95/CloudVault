"""Install the SQL-owned tables inside Django's isolated PostgreSQL test DB."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner


class CloudVaultTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        db_settings = settings.DATABASES["default"]
        test_name = db_settings.get("TEST", {}).get("NAME")
        if not test_name or test_name == db_settings["NAME"]:
            raise ImproperlyConfigured(
                "DB_TEST_NAME must name a separate database before running tests"
            )
        old_config = super().setup_databases(**kwargs)
        try:
            schema = Path(settings.BASE_DIR).parent / "database" / "schema.sql"
            with connections["default"].cursor() as cursor:
                cursor.execute(schema.read_text(encoding="utf-8"))
        except Exception:
            self.teardown_databases(old_config)
            raise
        return old_config
