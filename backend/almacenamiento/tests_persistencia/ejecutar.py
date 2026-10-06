"""Arranca PostgreSQL propio, instala la referencia literal, prueba y elimina.

Requiere initdb y pg_ctl locales de la misma instalación; sin Docker/red/.env.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg


def main():
    ejecutables = {nombre: shutil.which(nombre) for nombre in ("initdb", "pg_ctl")}
    if not all(ejecutables.values()):
        raise RuntimeError("Se necesitan initdb y pg_ctl de PostgreSQL local")
    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    with TemporaryDirectory(prefix="cv-fase02-", dir="/private/tmp") as temporal:
        directorio = Path(temporal)
        datos, socket = directorio / "datos", directorio / "socket"
        socket.mkdir(mode=0o700)
        token = uuid4().hex
        (directorio / ".cloudvault-fase2").write_text(token)
        argumentos_pg = [ejecutables["pg_ctl"], "-D", str(datos)]
        iniciado = False
        try:
            subprocess.run([ejecutables["initdb"], "-D", str(datos), "--auth-local=trust",
                            "--auth-host=reject", "--username=cloudvault_pruebas", "--no-locale",
                            "--encoding=UTF8"], check=True, capture_output=True, text=True)
            # Valores generados sin espacios. No escucha conexiones TCP.
            subprocess.run(argumentos_pg + ["-l", str(directorio / "postgres.log"), "-o",
                f"-k {socket} -p 65432 -c listen_addresses=''", "-w", "start"],
                check=True, capture_output=True, text=True)
            iniciado = True
            parametros = dict(host=str(socket), port=65432, user="cloudvault_pruebas")
            with psycopg.connect(dbname="postgres", autocommit=True, **parametros) as conn:
                conn.execute("CREATE DATABASE test_cloudvault_fase2")
            with psycopg.connect(dbname="test_cloudvault_fase2", **parametros) as conn:
                conn.execute((Path(__file__).with_name("prerrequisitos.sql")).read_text())
                conn.execute((repo / "agente/referencias/esquema-vigente.sql").read_text())
                print(f"PostgreSQL {conn.info.server_version}: esquema literal de 13 tablas instalado en clúster desechable.", flush=True)
            entorno = {**os.environ, "CLOUDVAULT_FASE2_TMP": temporal, "CLOUDVAULT_FASE2_TOKEN": token}
            resultado = subprocess.run([sys.executable, "-m", "django", "test",
                "almacenamiento.tests_persistencia", "almacenamiento.tests",
                "auth_workspaces.tests.test_error_security",
                "--settings=almacenamiento.tests_persistencia.settings", "--verbosity=2"],
                cwd=backend, env=entorno)
            return resultado.returncode
        except subprocess.CalledProcessError as error:
            print(error.stderr or error.stdout or "No se pudo arrancar PostgreSQL aislado", file=sys.stderr)
            log = directorio / "postgres.log"
            if log.is_file():
                print(log.read_text(), file=sys.stderr)
            return 1
        finally:
            if iniciado:
                subprocess.run(argumentos_pg + ["-m", "fast", "-w", "stop"], check=True,
                               capture_output=True, text=True)
            print("Clúster temporal detenido y eliminado; base de aplicación sin cambios.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
