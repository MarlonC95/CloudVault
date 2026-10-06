"""Ensayo opt-in con bytes sintéticos y claves únicas; sin Django/SQL/React.

Solo guarda indicadores sanitizados. No lista objetos ni cambia CORS/políticas.
"""

import argparse
import base64
import hashlib
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

import environ

from .configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida
from .s3 import ClienteS3, ErrorS3, PREFIJO_PROPIO


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def peticion(url, *, metodo="GET", cuerpo=None, headers=None):
    try:
        with build_opener(SinRedireccion()).open(
            Request(url, data=cuerpo, headers=headers or {}, method=metodo), timeout=20
        ) as respuesta:
            return respuesta.status, respuesta.read(65536), dict(respuesta.headers)
    except HTTPError as error:
        estado = error.code
        error.close()
        return estado, b"", {}
    except (URLError, OSError):
        raise ErrorS3("red") from None


def sin_firma(url):
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def ensayo(cliente, claves, informe):
    origen, destino, adverso, checksum = claves
    contenido = b"CloudVault: ensayo aislado de Dani, fase 03.\n"
    firma = cliente.firmar_put(origen, "text/plain")
    estado, _, headers = peticion(firma.url, metodo="PUT", cuerpo=contenido, headers=firma.encabezados)
    informe["put_estado_http"] = estado
    informe["put_firmado"] = estado in {200, 201, 204}
    if not informe["put_firmado"]:
        raise ErrorS3("put")
    objeto = cliente.consultar(origen)
    informe["head_tamano_mime"] = objeto.tamano_bytes == len(contenido) and objeto.tipo_mime == "text/plain"
    informe["etag_disponible"] = bool(objeto.etag)
    informe["version_devuelta"] = objeto.version is not None
    informe["hash_contenido"] = cliente.verificar_contenido(origen, maximo_bytes=len(contenido)).sha256 == hashlib.sha256(contenido).hexdigest()
    descarga = cliente.firmar_get(origen)
    estado, recibido, _ = peticion(descarga.url)
    informe["get_firmado_bytes_exactos"] = estado == 200 and recibido == contenido
    estado, _, _ = peticion(sin_firma(descarga.url))
    informe["get_anonimo_denegado"] = estado in {401, 403}
    copia = cliente.copiar(origen, destino, etag_origen=objeto.etag)
    informe["copia_bytes_exactos"] = copia.tamano_bytes == len(contenido) and cliente.verificar_contenido(destino, maximo_bytes=len(contenido)).sha256 == hashlib.sha256(contenido).hexdigest()
    try:
        cliente.copiar(origen, adverso, etag_origen='"etag-deliberadamente-distinto"')
        informe["copia_condicional_rechaza_etag_distinto"] = False
    except ErrorS3 as error:
        informe["copia_condicional_rechaza_etag_distinto"] = error.tipo == "precondicion"
    # Sonda separada: nunca convierte el checksum en requisito del PDF.
    try:
        cliente._operar("put_object", Key=checksum, Body=contenido, ContentType="text/plain",
                         ChecksumSHA256=base64.b64encode(hashlib.sha256(contenido).digest()).decode())
        respuesta = cliente._operar("head_object", Key=checksum, ChecksumMode="ENABLED")
        informe["checksum_sha256_retornado"] = respuesta.get("ChecksumSHA256") == base64.b64encode(hashlib.sha256(contenido).digest()).decode()
    except ErrorS3:
        informe["checksum_sha256_retornado"] = False
    breve = cliente.firmar_get(origen, vigencia=2)
    estado, _, _ = peticion(breve.url)
    informe["get_antes_de_expirar"] = estado == 200
    time.sleep(4)
    estado, _, _ = peticion(breve.url)
    informe["get_expirado_denegado"] = estado in {401, 403}
    breve_put = cliente.firmar_put(origen, "text/plain", vigencia=1)
    time.sleep(3)
    estado, _, _ = peticion(breve_put.url, metodo="PUT", cuerpo=contenido, headers=breve_put.encabezados)
    informe["put_expirado_denegado"] = estado in {401, 403}
    estado, _, cors = peticion(firma.url, metodo="OPTIONS", headers={
        "Origin": "http://127.0.0.1:8765", "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type"})
    informe["preflight_estado"] = estado
    informe["preflight_permite_origen"] = cors.get("Access-Control-Allow-Origin", cors.get("access-control-allow-origin")) in {"*", "http://127.0.0.1:8765"}


def ensayo_navegador(cliente, clave, informe):
    """Entrega firmas en memoria; solo el navegador recibe URLs transitorias."""
    config = {"put": cliente.firmar_put(clave, "text/plain").url,
              "get": cliente.firmar_get(clave).url}
    pagina = Path(__file__).with_name("ensayo_s3.html").read_bytes()
    terminado = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def enviar(self, cuerpo, tipo):
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == "/":
                self.enviar(pagina, "text/html; charset=utf-8")
            elif self.path == "/config":
                self.enviar(json.dumps(config).encode(), "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            nonlocal terminado
            if self.path != "/resultado":
                self.send_error(404)
                return
            try:
                largo = int(self.headers.get("Content-Length", "0"))
                if not 0 < largo <= 1024:
                    raise ValueError()
                datos = json.loads(self.rfile.read(largo))
                # Nunca persiste texto de errores, URLs ni datos arbitrarios.
                informe["navegador"] = {campo: datos.get(campo) is True for campo in ("put", "get", "bytes", "etag")}
                terminado = True
                self.enviar(b"{}", "application/json")
            except (ValueError, TypeError):
                self.send_error(400)

    with HTTPServer(("127.0.0.1", 8765), Handler) as servidor:
        servidor.timeout = 1
        print("Ensayo de navegador disponible en http://127.0.0.1:8765", flush=True)
        limite = time.monotonic() + 180
        while not terminado and time.monotonic() < limite:
            servidor.handle_request()
    if not terminado:
        informe["navegador"] = {"pendiente": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ejecutar", action="store_true", help="Crear y limpiar exclusivamente objetos nuevos de este ensayo")
    parser.add_argument("--perfil", choices=("railway", "minio"), default="railway")
    parser.add_argument("--navegador", action="store_true")
    parser.add_argument("--informe", type=Path)
    args = parser.parse_args()
    if not args.ejecutar:
        parser.error("El ensayo requiere --ejecutar; realiza escrituras temporales propias.")
    # No habilitar debug SDK/HTTP: puede contener firmas/encabezados privados.
    for nombre in ("boto3", "botocore", "urllib3"):
        logging.getLogger(nombre).setLevel(logging.CRITICAL)
    environ.Env.read_env(Path(__file__).resolve().parents[1] / ".env")
    informe = {"perfil": args.perfil, "prueba": str(uuid4())}
    prefijo = f"{PREFIJO_PROPIO}pruebas/{informe['prueba']}/"
    claves = [prefijo + str(uuid4()) for _ in range(5)]
    cliente = None
    try:
        cliente = ClienteS3(ConfiguracionS3.desde_entorno(perfil=args.perfil))
        ensayo(cliente, claves[:4], informe)
        if args.navegador:
            ensayo_navegador(cliente, claves[4], informe)
    except (ErrorS3, ConfiguracionS3Invalida) as error:
        informe["fallo"] = error.tipo if isinstance(error, ErrorS3) else "configuracion"
    except Exception:
        informe["fallo"] = "ensayo_incompleto"
    finally:
        limpieza = cliente is not None
        if cliente:
            for clave in claves:
                try:
                    cliente.borrar_tecnico(clave)
                    cliente.borrar_tecnico(clave)
                    try:
                        cliente.consultar(clave)
                        limpieza = False
                    except ErrorS3 as error:
                        limpieza = limpieza and error.tipo == "ausente"
                except ErrorS3 as error:
                    limpieza = False
                    informe["fallo_limpieza"] = error.tipo
            cliente.cerrar()
        informe["objetos_propios_limpiados"] = limpieza
    if args.informe:
        args.informe.write_text(json.dumps(informe, indent=2) + "\n")
    print(json.dumps(informe, indent=2))
    esenciales = ("put_firmado", "head_tamano_mime", "hash_contenido", "get_firmado_bytes_exactos",
                  "get_anonimo_denegado", "copia_bytes_exactos", "get_antes_de_expirar",
                  "get_expirado_denegado", "put_expirado_denegado", "objetos_propios_limpiados")
    aprobado = all(informe.get(campo) is True for campo in esenciales)
    if args.navegador:
        aprobado = aprobado and all(informe.get("navegador", {}).get(campo) is True for campo in ("put", "get", "bytes"))
    return 0 if aprobado and "fallo" not in informe else 1


if __name__ == "__main__":
    raise SystemExit(main())
