import json
from copy import deepcopy
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import resolve
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from jsonschema import Draft4Validator, FormatChecker

from almacenamiento.openapi import crear_openapi
from almacenamiento.contrato import PoliticaCarga
from almacenamiento.serializers import ConfirmarCargaInputSerializer, IniciarCargaInputSerializer
from .test_serializers import (
    ARCHIVO_ID, INICIO, RESPUESTA_CONFIRMACION, RESPUESTA_DESCARGA, RESPUESTA_INICIO,
)


def _json_schema(schema, documento):
    """Convertir el nullable de OpenAPI 3.0 para validar ejemplos con Draft 4."""
    if isinstance(schema, list):
        return [_json_schema(item, documento) for item in schema]
    if not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        result = documento
        for part in schema["$ref"].removeprefix("#/").split("/"):
            result = result[part]
        return _json_schema(result, documento)
    result = {key: _json_schema(value, documento) for key, value in schema.items()}
    if result.pop("nullable", False):
        result["type"] = [result["type"], "null"]
    return result


class OpenAPIContratoTests(SimpleTestCase):
    def setUp(self):
        self.documento = crear_openapi()

    def validar_ejemplo(self, nombre, body):
        schema = _json_schema(self.documento["components"]["schemas"][nombre], self.documento)
        return Draft4Validator(schema, format_checker=FormatChecker()).is_valid(body)

    def test_especificacion_openapi_valida(self):
        validate_schema(self.documento)

    def test_tres_rutas_pdf_status_y_bearer(self):
        expected = {
            "/api/v1/archivos/iniciar-carga/": ("post", "201"),
            "/api/v1/archivos/{id}/confirmar-carga/": ("post", "200"),
            "/api/v1/archivos/{id}/descarga/": ("get", "200"),
        }
        self.assertEqual(set(self.documento["paths"]), set(expected))
        for ruta, (metodo, status) in expected.items():
            operation = self.documento["paths"][ruta][metodo]
            self.assertIn(status, operation["responses"])
            self.assertEqual(operation["security"], [{"BearerAuth": []}])
            self.assertEqual(operation["x-estado-implementacion"], "endpoint-implementado-integracion-pendiente")
        inicio = self.documento["paths"]["/api/v1/archivos/iniciar-carga/"]["post"]
        self.assertIn("409", inicio["responses"])
        self.assertEqual(inicio["responses"]["409"]["description"], "CUOTA_EXCEDIDA")

    def test_ejemplos_de_request_y_response_validos(self):
        for nombre, body in (
            ("IniciarCargaInput", INICIO),
            ("ConfirmarCargaInput", {}),
            ("ConfirmarCargaInput", {"etag": '"valor-opcional"'}),
            ("IniciarCargaSuccess", RESPUESTA_INICIO),
            ("ConfirmarCargaSuccess", RESPUESTA_CONFIRMACION),
            ("DescargaSuccess", RESPUESTA_DESCARGA),
            ("Error", {"error": {"code": "CUOTA_EXCEDIDA", "fields": {}}}),
        ):
            with self.subTest(schema=nombre):
                self.assertTrue(self.validar_ejemplo(nombre, body))

    def test_openapi_y_validacion_coinciden_en_errores_de_entrada(self):
        casos = [
            {**INICIO, "tamano_bytes": True}, {**INICIO, "tamano_bytes": -1},
            {**INICIO, "tamano_bytes": "1024"}, {**INICIO, "carpeta_id": "documentos"},
            {**INICIO, "nombre": "../ruta.pdf"}, {**INICIO, "nombre": "  "},
            {**INICIO, "tipo_mime": "pdf"}, {**INICIO, "tipo_mime": "x\ny/z"},
            {**INICIO, "tipo_mime": "text/plain\n"},
            {**INICIO, "tamano_bytes": PoliticaCarga().maximo_archivo_bytes + 1},
            {**INICIO, "bucket": "ajeno"}, {**INICIO, "checksum_sha256": "a" * 64},
            {"nombre": INICIO["nombre"]}, [],
        ]
        for body in casos:
            with self.subTest(body=body):
                self.assertFalse(IniciarCargaInputSerializer(data=body).is_valid())
                self.assertFalse(self.validar_ejemplo("IniciarCargaInput", body))

    def test_raiz_opcional_y_etag_opcional_sin_header_extra_obligatorio(self):
        for body in ({**INICIO, "carpeta_id": None}, {k: v for k, v in INICIO.items() if k != "carpeta_id"}):
            self.assertTrue(IniciarCargaInputSerializer(data=body).is_valid())
            self.assertTrue(self.validar_ejemplo("IniciarCargaInput", body))
        self.assertTrue(ConfirmarCargaInputSerializer(data={}).is_valid())
        for path in self.documento["paths"].values():
            for operation in path.values():
                self.assertFalse(any(p["in"] == "header" for p in operation.get("parameters", [])))

    def test_openapi_admite_perfil_de_limite_operativo_configurado(self):
        documento = crear_openapi(politica=PoliticaCarga(maximo_archivo_bytes=1024))
        self.assertEqual(
            documento["components"]["schemas"]["IniciarCargaInput"]["properties"]["tamano_bytes"]["maximum"],
            1024,
        )

    def test_schema_no_admite_secretos_o_flags_coercionados_en_respuesta(self):
        body = deepcopy(RESPUESTA_INICIO)
        body["data"]["AWS_SECRET_ACCESS_KEY"] = "synthetic-not-real"
        self.assertFalse(self.validar_ejemplo("IniciarCargaSuccess", body))
        body = deepcopy(RESPUESTA_CONFIRMACION)
        body["data"]["en_papelera"] = "false"
        self.assertFalse(self.validar_ejemplo("ConfirmarCargaSuccess", body))

    def test_documento_exportado_coincide_con_generador(self):
        file = Path(__file__).resolve().parents[3] / "agente" / "contrato-fase-01.openapi.json"
        self.assertEqual(json.loads(file.read_text()), self.documento)

    def test_router_y_swagger_publican_las_tres_rutas_instaladas(self):
        for ruta in self.documento["paths"]:
            if "iniciar-carga" in ruta:
                self.assertEqual(resolve(ruta).url_name, "iniciar-carga")
                continue
            if "confirmar-carga" in ruta:
                self.assertEqual(resolve(ruta.replace("{id}", ARCHIVO_ID)).url_name, "confirmar-carga")
                continue
            self.assertEqual(resolve(ruta.replace("{id}", ARCHIVO_ID)).url_name, "descarga")
        installed = SchemaGenerator().get_schema(public=True)
        self.assertEqual(set(installed["paths"]), {
            "/api/v1/auth/registro/", "/api/v1/auth/login/",
            "/api/v1/auth/recuperar-contrasena/",
            "/api/v1/archivos/iniciar-carga/",
            "/api/v1/archivos/{id}/confirmar-carga/",
            "/api/v1/archivos/{id}/descarga/",
        })
        self.assertIn({"CloudVaultBearerAuth": []}, installed["paths"][
            "/api/v1/archivos/iniciar-carga/"]["post"]["security"])
        self.assertIn({"CloudVaultBearerAuth": []}, installed["paths"][
            "/api/v1/archivos/{id}/descarga/"]["get"]["security"])
