"""Pruebas de contrato sin .env, red, PostgreSQL, migraciones ni almacenamiento."""

SECRET_KEY = "synthetic-key-only-for-offline-contract-tests"
DEBUG = False
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "es"
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "drf_spectacular",
    "auth_workspaces",
    "almacenamiento",
]
AUTH_USER_MODEL = "auth_workspaces.Usuario"
DATABASES = {}
ROOT_URLCONF = "config.urls"
MIDDLEWARE = []
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "auth_workspaces.exceptions.api_exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "CloudVault API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
REGISTRATION_IP_RATE = "20/hour"
REGISTRATION_EMAIL_RATE = "5/hour"
LOGIN_IP_RATE = "20/hour"
LOGIN_EMAIL_RATE = "10/hour"
RECOVERY_IP_RATE = "20/hour"
RECOVERY_EMAIL_RATE = "5/hour"
AUTH_PASSWORD_VALIDATORS = []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
