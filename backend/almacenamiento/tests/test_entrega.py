"""Contrato entregable y guardas del cliente; sin .env, DB ni red."""

from copy import deepcopy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from jsonschema import Draft4Validator, FormatChecker
from rest_framework.test import APIClient

from almacenamiento.cliente_integracion import FalloIntegracion, RespuestaHTTP, TransporteHTTP, main, recorrer
from almacenamiento.contrato import OPERACIONES
from almacenamiento.openapi import crear_openapi, expandir_schema
from .test_openapi import _json_schema


ENTREGA = Path(__file__).resolve().parents[1] / "entrega"


class EntregaContratoTests(SimpleTestCase):
    def test_exportacion_entregable_actual_y_sin_rutas_inventadas(self):
        documento = json.loads((ENTREGA / "openapi.json").read_text())
        self.assertEqual(documento, crear_openapi())
        self.assertEqual(set(documento["paths"]), {o.ruta for o in OPERACIONES})
        validate_schema(documento)

    def test_ejemplos_ficticios_admitidos_por_contrato(self):
        documento = crear_openapi()
        ejemplos = json.loads((ENTREGA / "ejemplos.json").read_text())
        for nombre, body in ejemplos.items():
            if nombre == "advertencia":
                continue
            schema = documento["components"]["schemas"]["ConfirmarCargaInput" if nombre == "ConfirmarCargaConETag" else nombre]
            with self.subTest(nombre=nombre):
                Draft4Validator(_json_schema(schema, documento), format_checker=FormatChecker()).validate(body)
        for url in (ejemplos["IniciarCargaSuccess"]["data"]["url_subida"],
                    ejemplos["DescargaSuccess"]["data"]["url_descarga"]):
            self.assertIn("example.invalid", url)
            self.assertNotIn("X-Amz-", url)

    def test_swagger_y_exportacion_comparten_cuerpos_status_headers_y_uuid(self):
        documento = crear_openapi()
        swagger = SchemaGenerator().get_schema(public=True)
        validate_schema(swagger)
        for operacion in OPERACIONES:
            with self.subTest(ruta=operacion.ruta):
                declarado = documento["paths"][operacion.ruta][operacion.metodo.lower()]
                instalado = swagger["paths"][operacion.ruta][operacion.metodo.lower()]
                self.assertEqual(set(instalado["responses"]), set(declarado["responses"]))
                for status, response in declarado["responses"].items():
                    self.assertEqual(expandir_schema(response["content"]["application/json"]["schema"], documento),
                                     expandir_schema(instalado["responses"][status]["content"]["application/json"]["schema"], swagger))
                    self.assertEqual(set(instalado["responses"][status]["headers"]), set(response["headers"]))
                if "requestBody" in declarado:
                    self.assertEqual(bool(instalado["requestBody"].get("required")), declarado["requestBody"]["required"])
                    self.assertEqual(expandir_schema(declarado["requestBody"]["content"]["application/json"]["schema"], documento),
                                     expandir_schema(instalado["requestBody"]["content"]["application/json"]["schema"], swagger))
                else:
                    self.assertNotIn("requestBody", instalado)
                self.assertEqual(instalado.get("parameters", []), declarado.get("parameters", []))
                self.assertIn({"CloudVaultBearerAuth": []}, instalado["security"])

    def test_swagger_rechaza_tipos_coercionados_y_campos_extra(self):
        documento = SchemaGenerator().get_schema(public=True)
        schema = documento["paths"][OPERACIONES[0].ruta]["post"]["requestBody"]["content"]["application/json"]["schema"]
        validator = Draft4Validator(_json_schema(schema, documento), format_checker=FormatChecker())
        bueno = {"nombre": "ensayo.txt", "tipo_mime": "text/plain", "tamano_bytes": 5}
        self.assertTrue(validator.is_valid(bueno))
        for cambio in ({"tamano_bytes": True}, {"tamano_bytes": "5"}, {"bucket": "ajeno"},
                       {"nombre": "../otro"}, {"tipo_mime": "text/plain\n"}, {"carpeta_id": "no-uuid"}):
            with self.subTest(cambio=cambio):
                self.assertFalse(validator.is_valid({**bueno, **cambio}))

    @override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_errores_http_reales_y_headers_validan_contrato(self):
        documento = crear_openapi()
        for operacion in OPERACIONES:
            client = APIClient()
            ruta = operacion.ruta.replace("{id}", "22222222-2222-4222-8222-222222222222")
            respuestas = [client.generic(operacion.metodo, ruta)]
            client.credentials(HTTP_AUTHORIZATION="Bearer token-sintetico-invalido")
            respuestas.append(client.generic(operacion.metodo, ruta))
            client.credentials()
            client.force_authenticate(SimpleNamespace(pk="11111111-1111-4111-8111-111111111111", is_authenticated=True))
            respuestas.append(client.generic("POST" if operacion.metodo == "GET" else "GET", ruta))
            if operacion == OPERACIONES[0]:
                respuestas.append(client.post(ruta, {"tamano_bytes": True}, format="json"))
                respuestas.append(client.post(ruta, {"nombre": "x.txt", "tipo_mime": "text/plain", "tamano_bytes": 1}, format="json"))
            for respuesta in respuestas:
                with self.subTest(ruta=ruta, status=respuesta.status_code):
                    declarado = documento["paths"][operacion.ruta][operacion.metodo.lower()]["responses"][str(respuesta.status_code)]
                    Draft4Validator(_json_schema(declarado["content"]["application/json"]["schema"], documento)).validate(respuesta.data)
                    for nombre, header in declarado["headers"].items():
                        if nombre == "Retry-After":
                            continue
                        self.assertIn(respuesta[nombre], header["schema"]["enum"])


class ClienteGuardasTests(SimpleTestCase):
    def opciones(self, transporte):
        return dict(transporte=transporte, base_api="https://api.example.invalid",
                    origen_storage="https://storage.example.invalid", token="token-sintetico",
                    carpeta_id="11111111-1111-4111-8111-111111111111")

    def test_configuracion_invalida_no_hace_red(self):
        for cambios in ({"base_api": "http://remoto.example.invalid"}, {"base_api": "https://usuario:clave@api.example.invalid"},
                        {"base_api": "https://api.example.invalid/api/v1"}, {"token": ""}, {"token": "con\nsalto"},
                        {"origen_storage": "https://api.example.invalid"}, {"carpeta_id": "no-uuid"}):
            transporte = Mock()
            with self.subTest(cambios=cambios), self.assertRaises(FalloIntegracion):
                recorrer(**{**self.opciones(transporte), **cambios})
            transporte.solicitar.assert_not_called()

    def test_origen_storage_ajeno_se_rechaza_antes_de_put(self):
        documento = json.loads((ENTREGA / "ejemplos.json").read_text())
        body = deepcopy(documento["IniciarCargaSuccess"])
        body["data"]["url_subida"] = "https://ajeno.example.invalid/?firma=ficticia"
        transporte = Mock()
        transporte.solicitar.return_value = RespuestaHTTP(201, {}, json.dumps(body).encode())
        with self.assertRaises(FalloIntegracion) as exc:
            recorrer(**self.opciones(transporte))
        self.assertEqual(exc.exception.codigo, "ORIGEN_STORAGE_INCOMPATIBLE")
        self.assertEqual(transporte.solicitar.call_count, 1)
        self.assertIn("archivo_id", exc.exception.informe())

    def test_error_transporte_no_divulga_url_token_o_mensaje(self):
        transporte = Mock()
        transporte.solicitar.side_effect = RuntimeError("token-sintetico https://privado/?X-Amz-Signature=privado")
        with self.assertRaises(FalloIntegracion) as exc:
            recorrer(**self.opciones(transporte))
        informe = json.dumps(exc.exception.informe())
        for privado in ("token-sintetico", "https://", "X-Amz-Signature"):
            self.assertNotIn(privado, informe)

    def test_flag_obligatorio_antes_de_crear_transporte(self):
        with patch("almacenamiento.cliente_integracion.TransporteHTTP") as transporte, \
                patch("sys.stderr"), self.assertRaises(SystemExit) as salida:
            main(["--base-api", "https://api.example.invalid", "--origen-storage", "https://storage.example.invalid",
                  "--carpeta-id", "11111111-1111-4111-8111-111111111111"])
        self.assertEqual(salida.exception.code, 2)
        transporte.assert_not_called()

    def test_transporte_http_real_binario_redireccion_y_limite(self):
        recibidos = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_PUT(self):
                contenido = self.rfile.read(int(self.headers["Content-Length"]))
                recibidos.append((self.path, dict(self.headers), contenido))
                self.send_response(200)
                self.send_header("ETag", '"ficticio"')
                self.end_headers()

            def do_GET(self):
                recibidos.append((self.path, dict(self.headers), None))
                self.send_response(302 if self.path == "/redirigir" else 200)
                if self.path == "/redirigir":
                    self.send_header("Location", "/destino")
                self.end_headers()
                if self.path == "/excesivo":
                    self.wfile.write(b"x" * 65537)

        servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            origen = f"http://127.0.0.1:{servidor.server_port}"
            transporte = TransporteHTTP(timeout=2)
            respuesta = transporte.solicitar("PUT", origen + "/binario", headers={"Content-Type": "text/plain"}, body=b"\x00\xffbytes")
            self.assertEqual(respuesta.status, 200)
            self.assertEqual(respuesta.headers["ETag"], '"ficticio"')
            self.assertEqual(recibidos[0][2], b"\x00\xffbytes")
            self.assertNotIn("Authorization", recibidos[0][1])
            respuesta = transporte.solicitar("GET", origen + "/redirigir", headers={"Authorization": "Bearer token-sintetico"})
            self.assertEqual(respuesta.status, 302)
            self.assertNotIn("/destino", [r[0] for r in recibidos])
            with self.assertRaises(ValueError):
                transporte.solicitar("GET", origen + "/excesivo", headers={})
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(timeout=2)
