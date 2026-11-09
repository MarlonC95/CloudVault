"""Selección de panel: sin .env, DB, red ni migraciones."""
from auth_workspaces.tests_administracion_sin_bd.settings import *  # noqa: F403

INSTALLED_APPS = INSTALLED_APPS + ["storage", "almacenamiento", "drf_spectacular"]  # noqa: F405
ROOT_URLCONF = "config.urls"
ALMACENAMIENTO_URLCONFS_NEGOCIO = ("storage.urls", "subscriptions.urls")
