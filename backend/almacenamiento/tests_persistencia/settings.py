"""No lee .env. Solo acepta el clúster temporal creado por ejecutar.py."""

import os
from pathlib import Path

from almacenamiento.tests.settings import *  # noqa: F403

directorio = Path(os.environ.get("CLOUDVAULT_FASE2_TMP", "")).resolve()
marca = directorio / ".cloudvault-fase2"
if (directorio.parent != Path("/private/tmp") or not directorio.name.startswith("cv-fase02-")
        or not marca.is_file() or marca.read_text() != os.environ.get("CLOUDVAULT_FASE2_TOKEN")):
    raise RuntimeError("Ejecutar la suite con almacenamiento.tests_persistencia.ejecutar")
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "test_cloudvault_fase2",
    "USER": "cloudvault_pruebas",
    "HOST": str(directorio / "socket"),
    "PORT": "65432",
    "CONN_MAX_AGE": 0,
    "OPTIONS": {"connect_timeout": 5},
}}
TEST_RUNNER = "almacenamiento.tests_persistencia.runner.RunnerAislado"
