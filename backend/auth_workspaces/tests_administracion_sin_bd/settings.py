"""Selección aislada: sin .env, bases, migraciones, red ni runner SQL."""

from datetime import timedelta

SECRET_KEY = "synthetic-key-only-for-offline-administration-tests"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "auth_workspaces",
    "subscriptions",
]
AUTH_USER_MODEL = "auth_workspaces.Usuario"
DATABASES = {}
ROOT_URLCONF = "auth_workspaces.tests_administracion_sin_bd.urls"
TEST_RUNNER = (
    "auth_workspaces.tests_administracion_sin_bd.runner.RunnerAdministracionSinBD"
)
MIDDLEWARE = []
ALLOWED_HOSTS = ["testserver"]
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_PASSWORD_VALIDATORS = []
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "CHECK_REVOKE_TOKEN": True,
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
