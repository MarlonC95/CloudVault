"""Arranca PostgreSQL propio, instala la referencia literal, prueba y elimina.

Requiere initdb y pg_ctl locales de la misma instalación; sin Docker/red/.env.
"""

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory, mkdtemp
from uuid import uuid4

import psycopg

from .aceptacion import crear_informe, guardar_informe, metadatos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--informe", type=Path, help="Informe saneado de pruebas/matriz fase 8 (JSON)")
    parser.add_argument("--exigir-integracion", action="store_true",
                        help="Salir con código 2 si la integración completa sigue bloqueada")
    conservacion = parser.add_mutually_exclusive_group()
    conservacion.add_argument("--conservar-temporales", dest="conservar", action="store_true")
    conservacion.add_argument("--eliminar-temporales", dest="conservar", action="store_false",
                             help="Eliminar solo el clúster propio; requiere autorización explícita")
    parser.set_defaults(conservar=True)
    parser.add_argument("--perfil-auth-desplegado", action="store_true",
                        help="Regresión auth separada, en variante de fecha observada en la DB real")
    parser.add_argument("--evidencia-entorno-real", type=Path)
    args = parser.parse_args()
    if args.perfil_auth_desplegado:
        if not args.evidencia_entorno_real:
            parser.error("El perfil auth exige evidencia de lectura del esquema real")
        evidencia = json.loads(args.evidencia_entorno_real.read_text())
        if not (evidencia.get("consulta_sql_solo_lectura") is True and evidencia.get("sql_conectado") is True
                and evidencia.get("usuarios_columna_fecha_creacion") is True
                and evidencia.get("usuarios_columna_creado_en") is False):
            parser.error("La evidencia no acredita el mapping de fecha requerido")
    ejecutables = {nombre: shutil.which(nombre) for nombre in ("initdb", "pg_ctl")}
    if not all(ejecutables.values()):
        raise RuntimeError("Se necesitan initdb y pg_ctl de PostgreSQL local")
    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    contexto = metadatos(repo)
    resultados = []
    salida = 1
    temporal_eliminado = False
    temporal_contexto = (nullcontext(mkdtemp(prefix="cv-fase02-", dir="/private/tmp")) if args.conservar
                         else TemporaryDirectory(prefix="cv-fase02-", dir="/private/tmp"))
    with temporal_contexto as temporal:
        directorio = Path(temporal)
        datos, socket = directorio / "datos", directorio / "socket"
        socket.mkdir(mode=0o700)
        token = uuid4().hex
        (directorio / ".cloudvault-fase2").write_text(token)
        argumentos_pg = [ejecutables["pg_ctl"], "-D", str(datos)]
        inicio_pg = argumentos_pg + ["-l", str(directorio / "postgres.log"), "-o",
            f"-k {socket} -p 65432 -c listen_addresses=''", "-w", "start"]
        iniciado = False
        try:
            subprocess.run([ejecutables["initdb"], "-D", str(datos), "--auth-local=trust",
                            "--auth-host=reject", "--username=cloudvault_pruebas", "--no-locale",
                            "--encoding=UTF8"], check=True, capture_output=True, text=True)
            # Valores generados sin espacios. No escucha conexiones TCP.
            subprocess.run(inicio_pg,
                check=True, capture_output=True, text=True)
            iniciado = True
            parametros = dict(host=str(socket), port=65432, user="cloudvault_pruebas")
            with psycopg.connect(dbname="postgres", autocommit=True, **parametros) as conn:
                conn.execute("CREATE DATABASE test_cloudvault_fase2")
            with psycopg.connect(dbname="test_cloudvault_fase2", **parametros) as conn:
                conn.execute((Path(__file__).with_name("prerrequisitos.sql")).read_text())
                conn.execute((repo / "agente/referencias/esquema-vigente.sql").read_text())
                conn.execute((backend / "almacenamiento/sql/mantenimiento.sql").read_text())
                if args.perfil_auth_desplegado:
                    # Variante de fixture observada en DB real, nunca un alias
                    # para aprobar la suite literal: esta ejecución es distinta.
                    conn.execute("ALTER TABLE usuarios RENAME COLUMN creado_en TO fecha_creacion")
                    contexto["perfil"] = "AUTH_COMPAT_FECHA_OBSERVADA"
                    contexto["adaptacion_fixture"] = "Solo DB privada: usuarios.creado_en renombrado a fecha_creacion, como en la DB observada; no acredita compatibilidad del SQL literal."
                contexto["postgresql"] = conn.info.server_version
                print(f"PostgreSQL {conn.info.server_version}: 13 tablas instaladas en clúster privado; perfil "
                      + ("auth con mapping observado." if args.perfil_auth_desplegado else "SQL literal."), flush=True)
                print("Complemento propio de mantenimiento instalado solo en almacenamiento_tecnico.", flush=True)
            # Reinicio real del servidor propio. La fila centinela no es un mock
            # ni un dato de aplicación; no se altera el SQL literal para probarlo.
            centinela = uuid4()
            with psycopg.connect(dbname="test_cloudvault_fase2", **parametros) as conn:
                conn.execute("INSERT INTO organizaciones (id,nombre,slug) VALUES (%s,'Reinicio de ensayo',%s)",
                             [centinela, str(centinela)])
            subprocess.run(argumentos_pg + ["-m", "fast", "-w", "stop"], check=True, capture_output=True, text=True)
            iniciado = False
            subprocess.run(inicio_pg, check=True, capture_output=True, text=True)
            iniciado = True
            with psycopg.connect(dbname="test_cloudvault_fase2", **parametros) as conn:
                fila = conn.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [centinela]).fetchone()
                if fila != (0,):
                    raise RuntimeError("El reinicio no conservó el centinela")
                conn.execute("DELETE FROM organizaciones WHERE id=%s", [centinela])
            contexto["reinicio_postgresql_verificado"] = True
            ruta_resultados = directorio / "resultados.json"
            entorno = {**os.environ, "CLOUDVAULT_FASE2_TMP": temporal, "CLOUDVAULT_FASE2_TOKEN": token,
                       "CLOUDVAULT_RESULTADOS_FASE8": str(ruta_resultados)}
            etiquetas = ["almacenamiento.tests_persistencia", "almacenamiento.tests",
                         "auth_workspaces.tests.test_error_security"]
            settings_tests = "almacenamiento.tests_persistencia.settings"
            if args.perfil_auth_desplegado:
                etiquetas = ["auth_workspaces.tests.test_registro", "auth_workspaces.tests.test_login",
                             "auth_workspaces.tests.test_recovery", "auth_workspaces.tests.test_error_security"]
                settings_tests = "almacenamiento.tests_persistencia.settings_auth"
            if entorno.get("CLOUDVAULT_MINIO_PROPIO"):
                etiquetas.append("almacenamiento.tests_persistencia.minio_real")
                contexto["proveedor"] += "; MinIO local real en contenedor propio (negocio/JWT autorizado siguen sustituidos)"
            resultado = subprocess.run([sys.executable, "-m", "django", "test",
                *etiquetas,
                "--settings=" + settings_tests, "--verbosity=2"],
                cwd=backend, env=entorno)
            salida = resultado.returncode
            if ruta_resultados.is_file():
                resultados = json.loads(ruta_resultados.read_text())
        except subprocess.CalledProcessError as error:
            print(error.stderr or error.stdout or "No se pudo arrancar PostgreSQL aislado", file=sys.stderr)
            log = directorio / "postgres.log"
            if log.is_file():
                print(log.read_text(), file=sys.stderr)
        except Exception as error:
            # No serializar mensajes de DB/SDK ni datos privados del entorno.
            contexto["fallo_controlador"] = type(error).__name__
            print("No se completó el controlador aislado; informe marcado sin aprobación.", file=sys.stderr)
        finally:
            if iniciado:
                subprocess.run(argumentos_pg + ["-m", "fast", "-w", "stop"], check=True,
                               capture_output=True, text=True)
            print("Clúster propio detenido; temporales conservados." if args.conservar
                  else "Clúster propio detenido y eliminado.", flush=True)
    temporal_eliminado = not directorio.exists()
    contexto["temporales_conservados_por_instruccion"] = args.conservar
    if args.conservar:
        contexto["cluster_conservado"] = str(directorio)
    informe = crear_informe(resultados, contexto, salida=salida, limpio=temporal_eliminado)
    if args.perfil_auth_desplegado:
        requeridos_auth = {
            "auth_workspaces.tests.test_registro.RegistroTests.test_registro_crea_identidad_hashes_y_auditoria",
            "auth_workspaces.tests.test_login.LoginTests.test_credenciales_correctas_devuelven_200_usuario_y_jwt",
            "auth_workspaces.tests.test_recovery.RecuperacionTests.test_recuperacion_valida_cambia_solo_password_audita_e_invalida_access",
        }
        informe["regresion_auth_aprobada"] = (salida == 0 and bool(resultados)
            and all(r["estado"] == "APROBADO" for r in resultados)
            and requeridos_auth.issubset({r["id"] for r in resultados}))
        informe["ejecucion_local_aprobada"] = informe["regresion_auth_aprobada"]
    if args.informe:
        guardar_informe(args.informe, informe)
    print(json.dumps({"pruebas": informe["conteo_pruebas"], "matriz_local": informe["conteo_matriz_local"],
                      "integracion_completa_certificada": False}, ensure_ascii=False), flush=True)
    if salida:
        return salida
    if not informe["ejecucion_local_aprobada"]:
        return 1
    return 2 if args.exigir_integracion else 0


if __name__ == "__main__":
    sys.exit(main())
