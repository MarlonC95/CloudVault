"""Fase 8 con PostgreSQL y MinIO nuevos, sin .env/red remota/datos compartidos.

Requiere Docker activo e imagen MinIO disponible. Nunca descarga imágenes,
reutiliza contenedores, monta datos de aplicación ni escribe políticas Railway.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.probar_s3 import peticion
from almacenamiento.s3 import ClienteS3
from .aceptacion import combinar_minio, crear_informe, guardar_informe


IMAGEN = "minio/minio:RELEASE.2025-09-07T16-13-09Z"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directorio-informes", type=Path, required=True)
    parser.add_argument("--navegador", action="store_true")
    parser.add_argument("--duracion-navegador", type=int, default=180)
    parser.add_argument("--autorizar-limpieza-ensayo", action="store_true",
                        help="Requiere petición explícita del usuario para borrar solo los datos creados en este ensayo")
    args = parser.parse_args()
    if not args.autorizar_limpieza_ensayo:
        parser.error("Este controlador incluye limpieza real; no ejecutarlo sin autorización explícita del usuario")
    if not args.directorio_informes.is_dir() or not 1 <= args.duracion_navegador <= 240:
        parser.error("Se requiere un directorio existente y duración de navegador entre 1 y 240 segundos")
    docker = shutil.which("docker")
    if not docker:
        parser.error("Se requiere Docker local")
    nonce = uuid4().hex
    nombre = "cloudvault-fase8-" + nonce
    bucket = "fase8-" + nonce
    propietario = "cloudvault.fase8.propietario"
    entorno = {**os.environ, "MINIO_ROOT_USER": "ensayo" + uuid4().hex[:12],
               "MINIO_ROOT_PASSWORD": uuid4().hex,
               "MINIO_API_CORS_ALLOW_ORIGIN": "http://127.0.0.1:8765"}
    informe = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "prueba": nonce,
               "alcance": "PostgreSQL + MinIO reales y desechables; negocio/actor autorizado son fixtures",
               "imagen_solicitada": IMAGEN, "sin_env": True, "sin_pull": True,
               "contenedor_eliminado": False, "datos_minio_eliminados": False}
    creado = False
    salida = 1

    def comando(*argumentos):
        return subprocess.run([docker, *argumentos], check=True, capture_output=True,
                              text=True, env=entorno, timeout=30).stdout.strip()

    with TemporaryDirectory(prefix="cv-fase08-minio-", dir="/private/tmp") as temporal:
        datos = Path(temporal) / "datos"
        informes = Path(temporal) / "informes"
        datos.mkdir()
        informes.mkdir()
        sql_json, s3_json = None, None
        try:
            informe["etapa"] = "imagen"
            imagen = comando("image", "inspect", "--format", "{{.Id}}", IMAGEN)
            if not imagen.startswith("sha256:"):
                raise RuntimeError("Imagen no identificada")
            informe["imagen_id"] = imagen
            informe["etapa"] = "arranque"
            comando("run", "--detach", "--pull=never", "--name", nombre,
                    "--label", propietario + "=" + nonce, "--publish", "127.0.0.1::9000",
                    "--mount", "type=bind,src=" + str(datos) + ",dst=/data",
                    "--env", "MINIO_ROOT_USER", "--env", "MINIO_ROOT_PASSWORD",
                    "--env", "MINIO_API_CORS_ALLOW_ORIGIN", imagen, "server", "/data", "--address", ":9000")
            creado = True
            puerto = comando("port", nombre, "9000/tcp")
            if not puerto.startswith("127.0.0.1:") or not puerto.split(":")[-1].isdecimal():
                raise RuntimeError("MinIO no quedó limitado a loopback")
            endpoint = "http://" + puerto
            informe["etapa"] = "espera_inicial"
            limite = time.monotonic() + 20
            while True:
                try:
                    if peticion(endpoint + "/minio/health/ready")[0] == 200:
                        break
                except Exception:
                    pass
                if time.monotonic() >= limite:
                    raise RuntimeError("MinIO no inició")
                time.sleep(0.2)
            config = ConfiguracionS3("minio", endpoint, "us-east-1", bucket,
                                     entorno["MINIO_ROOT_USER"], entorno["MINIO_ROOT_PASSWORD"], estilo="path")
            cliente = ClienteS3(config)
            try:
                informe["etapa"] = "bucket_y_centinela"
                cliente._operar("create_bucket")
                centinela = "cloudvault/dani/pruebas/" + str(uuid4()) + "/" + str(uuid4())
                contenido = b"Ensayo de reinicio fase 8"
                cliente._operar("put_object", Key=centinela, Body=contenido, ContentType="text/plain")
                informe["etapa"] = "reinicio_minio"
                comando("restart", nombre)
                # Docker puede reasignar el puerto efímero al reiniciar. Leer
                # el nuevo binding propio; mantener siempre 127.0.0.1.
                nuevo_puerto = comando("port", nombre, "9000/tcp")
                if not nuevo_puerto.startswith("127.0.0.1:") or not nuevo_puerto.split(":")[-1].isdecimal():
                    raise RuntimeError("Binding de reinicio inválido")
                informe["puerto_cambio_durante_reinicio"] = nuevo_puerto != puerto
                endpoint = "http://" + nuevo_puerto
                cliente.cerrar()
                config = ConfiguracionS3("minio", endpoint, "us-east-1", bucket,
                    entorno["MINIO_ROOT_USER"], entorno["MINIO_ROOT_PASSWORD"], estilo="path")
                cliente = ClienteS3(config)
                informe["etapa"] = "espera_reinicio"
                limite = time.monotonic() + 20
                while True:
                    try:
                        if peticion(endpoint + "/minio/health/ready")[0] == 200:
                            break
                    except Exception:
                        pass
                    if time.monotonic() >= limite:
                        raise RuntimeError("MinIO no reinició")
                    time.sleep(0.2)
                informe["etapa"] = "hash_reinicio"
                if cliente.verificar_contenido(centinela, maximo_bytes=len(contenido)).sha256 != hashlib.sha256(contenido).hexdigest():
                    raise RuntimeError("Objeto no sobrevivió al reinicio")
                informe["reinicio_minio_hash_verificado"] = True
                cliente.borrar_tecnico(centinela)
                try:
                    cliente.consultar(centinela)
                except Exception as error:
                    if getattr(error, "tipo", None) != "ausente":
                        raise
                else:
                    raise RuntimeError("Centinela no eliminado")
            finally:
                cliente.cerrar()
            entorno.update(ALMACENAMIENTO_PERFIL="minio", S3_ENDPOINT_URL=endpoint,
                S3_REGION="us-east-1", S3_BUCKET=bucket, S3_ACCESS_KEY_ID=config.access_key,
                S3_SECRET_ACCESS_KEY=config.secret_key, S3_URL_STYLE="path", CLOUDVAULT_MINIO_PROPIO=nonce)
            backend = Path(__file__).resolve().parents[2]
            informe["etapa"] = "sql_s3"
            sql = subprocess.run([sys.executable, "-m", "almacenamiento.tests_persistencia.ejecutar",
                "--eliminar-temporales", "--informe", str(informes / "resultado-fase-08-minio-sql.json")], cwd=backend, env=entorno)
            informe["salida_sql_s3"] = sql.returncode
            informe["etapa"] = "firmas_y_navegador"
            flags = ["--navegador", "--duracion-navegador", str(args.duracion_navegador)] if args.navegador else []
            s3 = subprocess.run([sys.executable, "-m", "almacenamiento.probar_s3", "--ejecutar", "--perfil", "minio",
                "--sin-env", "--seguridad-fase8", "--limpiar-objetos", *flags, "--informe",
                str(informes / "resultado-fase-08-minio-s3.json")], cwd=backend, env=entorno)
            informe["salida_s3"] = s3.returncode
            informe["etapa"] = "consolidacion"
            informe["sha256_controlador"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            salida = 0 if sql.returncode == s3.returncode == 0 else 1
            sql_json = json.loads((informes / "resultado-fase-08-minio-sql.json").read_text())
            s3_json = json.loads((informes / "resultado-fase-08-minio-s3.json").read_text())
            for ruta in informes.glob("*.json"):
                informe["sha256_" + ruta.stem] = hashlib.sha256(ruta.read_bytes()).hexdigest()
                shutil.copyfile(ruta, args.directorio_informes / ruta.name)
            informe["etapa"] = "terminado"
        except Exception as error:
            informe["fallo_controlador"] = type(error).__name__
        finally:
            # run puede crear el contenedor y fallar al arrancarlo: comprobar
            # igualmente la identidad recién generada antes de limpiar.
            if creado or "imagen_id" in informe:
                # Solo borrar el contenedor recién creado y etiquetado por esta
                # ejecución. Nada de compose down/prune/volúmenes ajenos.
                try:
                    marca = comando("inspect", "--format", '{{ index .Config.Labels "' + propietario + '" }}', nombre)
                    if marca != nonce:
                        raise RuntimeError("Propietario de contenedor no coincide")
                    comando("rm", "--force", nombre)
                    informe["contenedor_eliminado"] = True
                except subprocess.CalledProcessError:
                    if creado:
                        informe["fallo_limpieza_contenedor"] = True
                        salida = 1
                except Exception:
                    informe["fallo_limpieza_contenedor"] = True
                    salida = 1
    informe["datos_minio_eliminados"] = not Path(temporal).exists()
    if not informe["datos_minio_eliminados"]:
        salida = 1
    (args.directorio_informes / "resultado-fase-08-minio-controlador.json").write_text(json.dumps(informe, indent=2) + "\n")
    if sql_json is not None and s3_json is not None:
        guardar_informe(args.directorio_informes / "resultado-fase-08-aceptacion.json", combinar_minio(sql_json, s3_json, informe))
    else:
        guardar_informe(args.directorio_informes / "resultado-fase-08-aceptacion.json",
            crear_informe([], informe, salida=1, limpio=informe["contenedor_eliminado"] and informe["datos_minio_eliminados"]))
    print(json.dumps(informe, indent=2), flush=True)
    return salida


if __name__ == "__main__":
    raise SystemExit(main())
