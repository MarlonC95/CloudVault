"""Ejemplo ejecutable de Mily: bytes sintéticos, URLs en memoria y sin limpieza.

No lee .env, obtiene credenciales S3, instala SQL ni configura proveedores.
El transporte se sustituye únicamente en tests privados declarados.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from .contrato import CodigoError, CONFIRMAR_CARGA, DESCARGA, INICIAR_CARGA


CONTENIDO = b"CloudVault fase 9"
NOMBRE = "ensayo-fase09.txt"


class FalloIntegracion(Exception):
    def __init__(self, etapa, *, codigo="RESPUESTA_INCOMPATIBLE", http=None):
        self.etapa, self.codigo, self.http = etapa, codigo, http
        super().__init__("No se completó el recorrido de integración.")

    def informe(self):
        informe = {"aprobado": False, "etapa": self.etapa, "codigo": self.codigo,
                   "http": self.http, "limpieza_ejecutada": False}
        if getattr(self, "archivo_id", None):
            informe["archivo_id"] = self.archivo_id
        return informe


@dataclass(frozen=True)
class RespuestaHTTP:
    status: int
    headers: dict
    body: bytes


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TransporteHTTP:
    def __init__(self, *, timeout=15):
        self.timeout = timeout
        self.opener = build_opener(SinRedireccion())

    def solicitar(self, metodo, url, *, headers, body=None):
        request = Request(url, method=metodo, headers=headers, data=body)
        try:
            respuesta = self.opener.open(request, timeout=self.timeout)
        except HTTPError as error:
            respuesta = error  # El cuerpo de error solo se procesa en memoria.
        with respuesta:
            contenido = respuesta.read(65537)
            if len(contenido) > 65536:
                raise ValueError("Respuesta fuera del límite del ejemplo")
            return RespuestaHTTP(respuesta.code, dict(respuesta.headers.items()), contenido)


def _origen(url):
    try:
        parsed = urlsplit(url)
        puerto = parsed.port
        if (parsed.username or parsed.password or not parsed.hostname
                or any(c.isspace() or ord(c) < 32 for c in url)
                or parsed.fragment or (puerto is not None and not 0 < puerto < 65536)
                or parsed.scheme not in {"https", "http"}
                or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})):
            raise ValueError
        return parsed.scheme, parsed.hostname, puerto or (443 if parsed.scheme == "https" else 80)
    except (TypeError, ValueError):
        raise FalloIntegracion("configuracion", codigo="CONFIGURACION_INVALIDA") from None


def _base(url):
    _origen(url)
    parsed = urlsplit(url)
    if parsed.path not in {"", "/"} or parsed.query:
        raise FalloIntegracion("configuracion", codigo="CONFIGURACION_INVALIDA")
    return url.rstrip("/")


def _vigente(valor, etapa):
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if fecha.utcoffset() != timezone.utc.utcoffset(None) or fecha <= datetime.now(timezone.utc):
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise FalloIntegracion(etapa, codigo="URL_VENCIDA_O_FECHA_INVALIDA") from None


def recorrer(**opciones):
    estado = {}
    try:
        return _recorrer(estado=estado, **opciones)
    except FalloIntegracion as error:
        error.archivo_id = estado.get("archivo_id")
        raise


def _recorrer(*, estado, transporte, base_api, token, origen_storage, carpeta_id):
    """Un inicio, un PUT, dos confirmaciones, autorización GET y bytes exactos.

    No reintenta fallos. El caller conserva archivo_id y decide con el dueño de
    cada dependencia; un fallo no provoca una sesión nueva ni compensaciones.
    """
    base_api, origen_storage = _base(base_api), _base(origen_storage)
    if (not isinstance(token, str) or not token or any(c.isspace() for c in token)
            or _origen(base_api) == _origen(origen_storage)):
        raise FalloIntegracion("configuracion", codigo="CONFIGURACION_INVALIDA")
    try:
        if str(UUID(carpeta_id)) != carpeta_id.lower():
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise FalloIntegracion("configuracion", codigo="CONFIGURACION_INVALIDA") from None

    archivo_id = None

    def solicitar(etapa, metodo, url, headers, body=None):
        try:
            return transporte.solicitar(metodo, url, headers=headers, body=body)
        except Exception:
            raise FalloIntegracion(etapa, codigo="TRANSPORTE_NO_DISPONIBLE") from None

    def api(etapa, operacion, datos=None):
        url = base_api + operacion.ruta.replace("{id}", archivo_id or "")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if datos is not None:
            headers["Content-Type"] = "application/json"
        respuesta = solicitar(etapa, operacion.metodo, url, headers,
                              json.dumps(datos).encode() if datos is not None else None)
        try:
            body = json.loads(respuesta.body)
        except (ValueError, UnicodeError):
            raise FalloIntegracion(etapa, http=respuesta.status) from None
        if respuesta.status != operacion.estado_exito:
            codigo = body.get("error", {}).get("code") if isinstance(body, dict) and isinstance(body.get("error"), dict) else None
            codigo = codigo if codigo in {c.value for c in CodigoError} else "RESPUESTA_INCOMPATIBLE"
            raise FalloIntegracion(etapa, codigo=codigo, http=respuesta.status)
        if not isinstance(body, dict) or set(body) != {"data"} or not isinstance(body["data"], dict):
            raise FalloIntegracion(etapa, http=respuesta.status)
        return body["data"]

    def url_storage(url, etapa):
        try:
            valido = _origen(url) == _origen(origen_storage)
        except FalloIntegracion:
            valido = False
        if not valido:
            raise FalloIntegracion(etapa, codigo="ORIGEN_STORAGE_INCOMPATIBLE")
        return url  # Se usa literalmente: nunca editar host, path ni firma.

    inicio = api("iniciar", INICIAR_CARGA, {"nombre": NOMBRE, "tamano_bytes": len(CONTENIDO),
                 "tipo_mime": "text/plain", "carpeta_id": carpeta_id})
    try:
        if (set(inicio) != {"archivo_id", "url_subida", "metodo", "encabezados", "expira_en"}
                or inicio["metodo"] != "PUT" or inicio["encabezados"] != {"Content-Type": "text/plain"}
                or str(UUID(inicio["archivo_id"])) != inicio["archivo_id"].lower()):
            raise ValueError
        archivo_id = inicio["archivo_id"]
        estado["archivo_id"] = archivo_id
    except (ValueError, KeyError, TypeError, AttributeError):
        raise FalloIntegracion("iniciar") from None
    _vigente(inicio["expira_en"], "put")
    subida = solicitar("put", inicio["metodo"], url_storage(inicio["url_subida"], "put"),
                       inicio["encabezados"], CONTENIDO)
    if subida.status != 200:
        raise FalloIntegracion("put", codigo="PUT_RECHAZADO", http=subida.status)
    etag = next((v for k, v in subida.headers.items() if k.lower() == "etag"), None)
    body_confirmacion = {"etag": etag} if isinstance(etag, str) and etag else {}
    confirmacion = api("confirmar", CONFIRMAR_CARGA, body_confirmacion)
    if (set(confirmacion) != {"id", "nombre", "es_nuevo", "en_papelera"}
            or confirmacion["id"] != archivo_id or confirmacion["nombre"] != NOMBRE
            or type(confirmacion["es_nuevo"]) is not bool or confirmacion["en_papelera"] is not False):
        raise FalloIntegracion("confirmar")
    repetida = api("repetir_confirmacion", CONFIRMAR_CARGA, body_confirmacion)
    if repetida != confirmacion:
        raise FalloIntegracion("repetir_confirmacion")
    descarga = api("autorizar_descarga", DESCARGA)
    if set(descarga) != {"url_descarga", "nombre", "expira_en"} or descarga["nombre"] != NOMBRE:
        raise FalloIntegracion("autorizar_descarga")
    _vigente(descarga["expira_en"], "get")
    contenido = solicitar("get", "GET", url_storage(descarga["url_descarga"], "get"), {})
    if contenido.status != 200 or contenido.body != CONTENIDO:
        raise FalloIntegracion("get", codigo="CONTENIDO_NO_VERIFICADO", http=contenido.status)
    return {"aprobado": True, "archivo_id": archivo_id, "bytes": len(CONTENIDO),
            "sha256": hashlib.sha256(CONTENIDO).hexdigest(), "confirmacion_repetida_identica": True,
            "etag_disponible": etag is not None, "limpieza_ejecutada": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ejecutar", action="store_true", help="Crear un archivo sintético de 17 bytes; conservarlo")
    parser.add_argument("--base-api", required=True, help="Origen HTTPS de API o HTTP loopback local")
    parser.add_argument("--origen-storage", required=True, help="Origen exacto esperado en las URLs S3 firmadas")
    parser.add_argument("--carpeta-id", required=True)
    parser.add_argument("--informe", type=Path)
    args = parser.parse_args(argv)
    if not args.ejecutar:
        parser.error("El cliente solo ejecuta con --ejecutar; no hace red ni modifica datos sin ese flag")
    try:
        resultado = recorrer(transporte=TransporteHTTP(), base_api=args.base_api,
            origen_storage=args.origen_storage, carpeta_id=args.carpeta_id,
            token=os.environ.get("ALMACENAMIENTO_TOKEN_PRUEBA", ""))
    except FalloIntegracion as error:
        resultado = error.informe()
    resultado["fecha_utc"] = datetime.now(timezone.utc).isoformat()
    resultado["perfil"] = "API_CONFIGURADA_POR_OPERADOR"
    serializado = json.dumps(resultado, ensure_ascii=False, indent=2) + "\n"
    if args.informe:
        args.informe.write_text(serializado, encoding="utf-8")
    print(serializado, end="")
    return 0 if resultado["aprobado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
