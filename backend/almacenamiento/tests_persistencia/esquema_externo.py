"""Lee el esquema del responsable SQL sin copiarlo ni modificar otras ramas.

El consumidor ejecuta este texto exclusivamente en su PostgreSQL privado.
Una referencia Git se resuelve a un commit antes de leer el archivo para que
la evidencia identifique el esquema exacto que se probó.
"""

import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess


REFERENCIA_PREDETERMINADA = "origin/feature/auth-custom-user-jwt"
RUTA_PREDETERMINADA = "database/schema.sql"


def cargar_esquema(repo, *, archivo=None, referencia=REFERENCIA_PREDETERMINADA,
                   ruta=RUTA_PREDETERMINADA):
    try:
        if archivo is not None:
            contenido = Path(archivo).read_bytes()
            origen = {"tipo": "archivo_externo", "nombre": Path(archivo).name}
        else:
            partes = PurePosixPath(ruta)
            if (not referencia or referencia.startswith("-") or any(c.isspace() for c in referencia)
                    or not ruta or partes.is_absolute() or ".." in partes.parts
                    or "\\" in ruta or str(partes) != ruta):
                raise ValueError("Referencia o ruta de esquema inválida")
            entorno = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
            commit = subprocess.run(
                ["git", "rev-parse", "--verify", referencia + "^{commit}"],
                cwd=repo, env=entorno, check=True, capture_output=True, text=True,
            ).stdout.strip()
            contenido = subprocess.run(
                ["git", "show", commit + ":" + ruta], cwd=repo, env=entorno,
                check=True, capture_output=True,
            ).stdout
            origen = {"tipo": "git", "commit": commit, "ruta": ruta}
        texto = contenido.decode("utf-8")
        if not texto.strip():
            raise ValueError("Esquema vacío")
    except (OSError, UnicodeError, subprocess.CalledProcessError, ValueError):
        raise ValueError("No se pudo leer el esquema completo del responsable SQL; "
                         "proporcionar --esquema o una referencia Git disponible.") from None
    return texto, {**origen, "sha256": hashlib.sha256(contenido).hexdigest()}


def verificar_diario(conn):
    if not conn.execute("SELECT to_regclass('public.trabajos_mantenimiento') IS NOT NULL").fetchone()[0]:
        raise ValueError("El esquema de pruebas debe incluir public.trabajos_mantenimiento.")
