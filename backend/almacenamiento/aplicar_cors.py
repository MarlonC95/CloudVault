"""Configura exclusivamente CORS del bucket Railway; sin escribir objetos.

Sin --aplicar solo consulta y comprueba OPTIONS. Los secretos se leen del .env
local; no se imprimen respuestas SDK completas ni URLs temporales.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from uuid import uuid4

import environ
from botocore.exceptions import BotoCoreError, ClientError

from .configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida
from .cors import ORIGEN_ENSAYO, evaluar_preflight
from .probar_s3 import peticion
from .s3 import ClienteS3, ErrorS3


def politica(origenes):
    for origen in origenes:
        try:
            url = urlsplit(origen)
            valido = (url.scheme in {"http", "https"} and url.hostname
                      and not url.username and not url.password and not url.path
                      and not url.query and not url.fragment
                      and "*" not in origen and not any(c.isspace() for c in origen)
                      and (url.port is None or 0 < url.port < 65536))
        except ValueError:
            valido = False
        if not valido:
            raise ValueError("Origen inválido; usar protocolo, host y puerto, sin ruta.")
    if not origenes:
        raise ValueError("Se requiere un origen.")
    return {"ID": "CloudVaultEnsayo", "AllowedOrigins": list(dict.fromkeys(origenes)),
            "AllowedMethods": ["PUT", "GET"], "AllowedHeaders": ["content-type"],
            "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 300}


def _regla_legible(regla):
    if not isinstance(regla, dict):
        return False
    for campo in ("AllowedOrigins", "AllowedMethods", "AllowedHeaders", "ExposeHeaders"):
        obligatorio = campo in ("AllowedOrigins", "AllowedMethods")
        if obligatorio or campo in regla:
            valores = regla.get(campo)
            if (not isinstance(valores, list) or (obligatorio and not valores)
                    or any(not isinstance(valor, str) or not valor for valor in valores)):
                return False
    return (("ID" not in regla or isinstance(regla["ID"], str))
            and ("MaxAgeSeconds" not in regla
                 or (type(regla["MaxAgeSeconds"]) is int and regla["MaxAgeSeconds"] >= 0)))


def consultar_cors(cliente):
    try:
        respuesta = cliente._cliente.get_bucket_cors(Bucket=cliente.configuracion.bucket)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "NoSuchCORSConfiguration":
            return {"estado": "ausente", "CORSRules": []}
        raise
    reglas = respuesta.get("CORSRules") if isinstance(respuesta, dict) else None
    if not isinstance(reglas, list) or not all(_regla_legible(regla) for regla in reglas):
        return {"estado": "no_verificable", "CORSRules": None}
    return {"estado": "presente" if reglas else "vacio", "CORSRules": reglas}


def guardar_respaldo(anterior, propuesta):
    carpeta = Path(tempfile.mkdtemp(prefix="cloudvault-cors-"))
    os.chmod(carpeta, 0o700)
    for nombre, datos in (("estado-anterior.json", anterior),
                           ("propuesta.json", propuesta)):
        archivo = carpeta / nombre
        with archivo.open("x", encoding="utf-8") as stream:
            os.chmod(archivo, 0o600)
            json.dump(datos, stream, indent=2)
            stream.write("\n")
    # El respaldo S3 restaurable solo existe si el proveedor devolvió reglas.
    if anterior["estado"] == "presente":
        archivo = carpeta / "cors-restaurable.json"
        with archivo.open("x", encoding="utf-8") as stream:
            os.chmod(archivo, 0o600)
            json.dump({"CORSRules": anterior["CORSRules"]}, stream, indent=2)
    return str(carpeta)


def regla_verificada(estado, regla):
    def contiene(actual):
        return (set(regla["AllowedOrigins"]) <= set(actual.get("AllowedOrigins", []))
                and set(regla["AllowedMethods"]) <= set(actual.get("AllowedMethods", []))
                and ("*" in actual.get("AllowedHeaders", []) or "content-type" in {
                    h.lower() for h in actual.get("AllowedHeaders", [])})
                and "etag" in {h.lower() for h in actual.get("ExposeHeaders", [])})
    return any(contiene(actual) for actual in estado.get("CORSRules") or [])


def comprobar_options(cliente, origenes):
    clave = f"cloudvault/dani/pruebas/{uuid4()}/{uuid4()}"
    firma = cliente.firmar_put(clave, "text/plain")
    resultados = []
    for origen in origenes:
        estado, _, headers = peticion(firma.url, metodo="OPTIONS", headers={
            "Origin": origen, "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type"})
        resultados.append({"origen": origen, **evaluar_preflight(estado, headers, origen=origen)})
    return resultados


def ejecutar(cliente, origenes, *, aplicar=False):
    regla = politica(origenes)
    anterior = consultar_cors(cliente)
    informe = {"lectura_previa": anterior["estado"], "escritura_solicitada": aplicar}
    if aplicar and anterior["estado"] == "no_verificable":
        # No existe una política previa recuperable. Detener antes de respaldo,
        # PUT o preflight; una respuesta 200 incompleta no demuestra ausencia.
        informe.update(lectura_final=anterior["estado"], regla_verificada=False,
                       preflight=[], aprobado=False, error="lectura_previa_no_verificable")
        return informe
    if aplicar:
        # Conserva reglas ajenas; sustituye únicamente nuestra regla identificada.
        reglas = [r for r in anterior["CORSRules"] if r.get("ID") != regla["ID"]]
        propuesta = {"CORSRules": reglas + [regla]}
        if len(propuesta["CORSRules"]) > 100:
            raise ValueError("Demasiadas reglas CORS; no se escribió la configuración.")
        informe["respaldo"] = guardar_respaldo(anterior, propuesta)
        print(json.dumps({"respaldo": informe["respaldo"],
                          "lectura_previa": anterior["estado"]}), flush=True)
        cliente._cliente.put_bucket_cors(Bucket=cliente.configuracion.bucket,
                                        CORSConfiguration=propuesta)
        informe["operacion_put_cors_respondio"] = True
    actual = consultar_cors(cliente) if aplicar else anterior
    informe["lectura_final"] = actual["estado"]
    informe["regla_verificada"] = regla_verificada(actual, regla)
    informe["preflight"] = comprobar_options(cliente, origenes)
    informe["aprobado"] = informe["regla_verificada"] and all(
        r["aprobado"] for r in informe["preflight"])
    # Nunca borra CORS como reversión de una lectura no verificable.
    return informe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--origen", action="append", help="Repetible; defecto: origen del ensayo")
    args = parser.parse_args()
    cliente = None
    try:
        origenes = args.origen or [ORIGEN_ENSAYO]
        politica(origenes)  # Validar antes de consultar o escribir.
        for nombre in ("boto3", "botocore", "urllib3"):
            logging.getLogger(nombre).setLevel(logging.CRITICAL)
        # Fuente explícita local; no reutiliza credenciales antiguas exportadas.
        environ.Env.read_env(Path(__file__).resolve().parents[1] / ".env", overwrite=True)
        cliente = ClienteS3(ConfiguracionS3.desde_entorno(perfil="railway"))
        informe = ejecutar(cliente, origenes, aplicar=args.aplicar)
        print(json.dumps(informe, indent=2))
        return 0 if informe["aprobado"] else 1
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code")
        seguros = {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch",
                   "NotImplemented", "MethodNotAllowed", "InvalidRequest"}
        print(json.dumps({"aprobado": False, "error": codigo if codigo in seguros else "error_proveedor",
                          "estado_http": exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")}))
        return 1
    except (BotoCoreError, ErrorS3, ConfiguracionS3Invalida, ValueError, OSError):
        print(json.dumps({"aprobado": False, "error": "configuracion_red_o_respaldo"}))
        return 1
    finally:
        if cliente:
            cliente.cerrar()


if __name__ == "__main__":
    raise SystemExit(main())
