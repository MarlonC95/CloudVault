"""CloudVault API settings."""

from pathlib import Path
from datetime import timedelta

import environ
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / ".env")
env = environ.Env()

DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY", default="").strip()
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required")

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"]
)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "auth_workspaces",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# Solo la API acepta solicitudes desde el frontend configurado. En desarrollo
# se permiten las dos direcciones habituales del servidor Vite local.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"] if DEBUG else [],
)
CORS_URLS_REGEX = r"^/api/"
CORS_ALLOW_CREDENTIALS = False

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_url = env("DATABASE_URL", default="").strip()
if database_url:
    DATABASES = {"default": env.db_url_config(database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": env("DB_ENGINE", default="django.db.backends.postgresql"),
            "NAME": env("DB_NAME", default=""),
            "USER": env("DB_USER", default=""),
            "PASSWORD": env("DB_PASSWORD", default=""),
            "HOST": env("DB_HOST", default=""),
            "PORT": env("DB_PORT", default="5432"),
        }
    }

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("CloudVault requires PostgreSQL")

DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
sslmode = env("DB_SSLMODE", default="").strip()
if sslmode:
    DATABASES["default"].setdefault("OPTIONS", {}).setdefault("sslmode", sslmode)
test_name = env("DB_TEST_NAME", default="").strip()
if test_name:
    DATABASES["default"]["TEST"] = {"NAME": test_name}

AUTH_USER_MODEL = "auth_workspaces.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("correo_electronico", "nombre_completo")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "auth_workspaces.authentication.CloudVaultJWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "auth_workspaces.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "NUM_PROXIES": 0,
}

REGISTRATION_IP_RATE = env("REGISTRATION_IP_RATE", default="20/hour")
REGISTRATION_EMAIL_RATE = env("REGISTRATION_EMAIL_RATE", default="5/hour")
LOGIN_IP_RATE = env("LOGIN_IP_RATE", default="20/hour")
LOGIN_EMAIL_RATE = env("LOGIN_EMAIL_RATE", default="10/hour")
RECOVERY_IP_RATE = env("RECOVERY_IP_RATE", default="20/hour")
RECOVERY_EMAIL_RATE = env("RECOVERY_EMAIL_RATE", default="5/hour")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "CHECK_REVOKE_TOKEN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CloudVault API",
    "DESCRIPTION": "Registro, inicio de sesión y recuperación de contraseña",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "es"
TEST_RUNNER = "config.test_runner.CloudVaultTestRunner"

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
