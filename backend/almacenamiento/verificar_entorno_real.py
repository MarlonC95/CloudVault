"""Diagnóstico de configuración y PostgreSQL real, exclusivamente de lectura.

No crea/borra/migra tablas, no consulta datos de personas y no imprime secretos.
Se ejecuta solo a petición del usuario; la suite aislada nunca lo invoca.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import environ
import psycopg

from .configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--informe", type=Path, required=True)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    archivo_env = backend / ".env"
    original = hashlib.sha256(archivo_env.read_bytes()).hexdigest()
    environ.Env.read_env(archivo_env, overwrite=True)
    informe = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "consulta_sql_solo_lectura": True,
               "datos_de_negocio_consultados": False, "sql_conectado": False}
    try:
        ConfiguracionS3.desde_entorno(perfil="railway")
        informe["configuracion_s3_valida"] = True
    except ConfiguracionS3Invalida:
        informe["configuracion_s3_valida"] = False
    informe["proveedor_negocio_configurado_en_env"] = bool(os.environ.get("ALMACENAMIENTO_SERVICIOS_FACTORY"))
    try:
        if os.environ.get("DATABASE_URL", "").strip():
            cfg = environ.Env.db_url_config(os.environ["DATABASE_URL"])
        else:
            cfg = {"ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
                   **{k: os.environ.get("DB_"+k, "") for k in ("HOST","NAME","USER","PASSWORD","PORT")}}
        if cfg["ENGINE"] != "django.db.backends.postgresql" or any(not cfg[k] for k in ("HOST","NAME","USER","PASSWORD")):
            raise ValueError("Configuración PostgreSQL incompleta")
        parametros = {"dbname": cfg["NAME"], "host": cfg["HOST"], "user": cfg["USER"],
                      "password": cfg["PASSWORD"], "port": cfg.get("PORT") or "5432", "connect_timeout": 5,
                      "options": "-c default_transaction_read_only=on -c statement_timeout=5000"}
        sslmode = os.environ.get("DB_SSLMODE") or cfg.get("OPTIONS", {}).get("sslmode")
        if sslmode:
            parametros["sslmode"] = sslmode
        with psycopg.connect(**parametros) as conn:
            if conn.execute("SHOW transaction_read_only").fetchone() != ("on",):
                raise RuntimeError("La conexión no es de solo lectura")
            informe["sql_conectado"] = True
            informe["postgresql"] = conn.info.server_version
            referencia = (backend.parent / "agente/referencias/esquema-vigente.sql").read_text()
            tablas = re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", referencia)
            informe["tablas_referencia_disponibles"] = {
                t: conn.execute("SELECT to_regclass(%s) IS NOT NULL", ["public."+t]).fetchone()[0] for t in tablas}
            informe["diario_mantenimiento_disponible"] = conn.execute(
                "SELECT to_regclass('almacenamiento_tecnico.trabajos_mantenimiento') IS NOT NULL").fetchone()[0]
            for nombre in ("fecha_creacion", "creado_en"):
                informe["usuarios_columna_" + nombre] = conn.execute("""SELECT EXISTS(
                    SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                    AND table_name='usuarios' AND column_name=%s)""", [nombre]).fetchone()[0]
    except Exception as error:
        informe["fallo_sql_tipo"] = type(error).__name__
    informe["env_sin_cambios"] = hashlib.sha256(archivo_env.read_bytes()).hexdigest() == original
    args.informe.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["sql_conectado"] and informe["env_sin_cambios"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
