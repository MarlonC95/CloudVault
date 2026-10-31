"""Pruebas aisladas de storage: sin .env, conexiones o creación de BD."""
from almacenamiento.tests.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "storage", "subscriptions"]  # noqa: F405
ALMACENAMIENTO_URLCONFS_NEGOCIO = ["storage.urls", "subscriptions.urls"]
