"""CORS: respuestas 200 incompletas, respaldo y conservación de reglas ajenas."""

import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from django.test import SimpleTestCase

from almacenamiento import aplicar_cors
from almacenamiento.cors import ORIGEN_ENSAYO, evaluar_preflight


class CorsTests(SimpleTestCase):
    def headers(self):
        return {"ACCESS-CONTROL-ALLOW-ORIGIN": ORIGEN_ENSAYO,
                "Access-Control-Allow-Methods": "GET, PUT",
                "Access-control-allow-headers": "Content-Type"}

    def test_mayusculas_no_alteran_validacion(self):
        self.assertTrue(evaluar_preflight(200, self.headers())["aprobado"])

    def test_200_no_certifica_headers_ausentes(self):
        self.assertFalse(evaluar_preflight(200, {})["aprobado"])
        for nombre in self.headers():
            headers = self.headers()
            del headers[nombre]
            self.assertFalse(evaluar_preflight(200, headers)["aprobado"])

    def test_origen_exacto_metodo_y_header_requeridos(self):
        for nombre, valor in (("ACCESS-CONTROL-ALLOW-ORIGIN", "*"),
                              ("Access-Control-Allow-Methods", "GET"),
                              ("Access-control-allow-headers", "authorization")):
            headers = self.headers()
            headers[nombre] = valor
            self.assertFalse(evaluar_preflight(200, headers)["aprobado"])
        self.assertFalse(evaluar_preflight(403, self.headers())["aprobado"])

    def test_politica_minima_y_origenes_invalidos(self):
        regla = aplicar_cors.politica([ORIGEN_ENSAYO])
        self.assertEqual(regla["AllowedMethods"], ["PUT", "GET"])
        self.assertEqual(regla["AllowedHeaders"], ["content-type"])
        self.assertEqual(regla["ExposeHeaders"], ["ETag"])
        for origen in ("*", "null", ORIGEN_ENSAYO + "/", "https://u:p@example.test",
                       "https://example.test?query=1"):
            with self.subTest(origen=origen), self.assertRaises(ValueError):
                aplicar_cors.politica([origen])

    def test_metadata_sola_no_significa_regla_vacia(self):
        cliente = Mock()
        cliente._cliente.get_bucket_cors.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        self.assertEqual(aplicar_cors.consultar_cors(cliente)["estado"], "no_verificable")

    def test_no_such_cors_no_oculta_access_denied(self):
        cliente = Mock()
        for codigo in ("NoSuchCORSConfiguration", "AccessDenied"):
            cliente._cliente.get_bucket_cors.side_effect = ClientError(
                {"Error": {"Code": codigo}}, "GetBucketCors")
            if codigo == "NoSuchCORSConfiguration":
                self.assertEqual(aplicar_cors.consultar_cors(cliente)["estado"], "ausente")
            else:
                with self.assertRaises(ClientError):
                    aplicar_cors.consultar_cors(cliente)

    def test_preserva_reglas_ajenas_y_respalda_antes_de_escribir(self):
        cliente = Mock()
        ajena = {"ID": "otra-app", "AllowedOrigins": ["https://example.test"],
                 "AllowedMethods": ["GET"]}
        regla = aplicar_cors.politica([ORIGEN_ENSAYO])
        cliente._cliente.get_bucket_cors.side_effect = [
            {"CORSRules": [ajena]}, {"CORSRules": [ajena, regla]}]
        with patch.object(aplicar_cors, "guardar_respaldo", return_value="/tmp/respaldo") as respaldo, \
             patch.object(aplicar_cors, "comprobar_options", return_value=[{"aprobado": True}]):
            def escribir(**kwargs):
                respaldo.assert_called_once()
                self.assertEqual(kwargs["CORSConfiguration"]["CORSRules"], [ajena, regla])
            cliente._cliente.put_bucket_cors.side_effect = escribir
            self.assertTrue(aplicar_cors.ejecutar(cliente, [ORIGEN_ENSAYO], aplicar=True)["aprobado"])
        cliente._cliente.delete_bucket_cors.assert_not_called()

    def test_put_200_sin_reglas_ni_cors_no_es_exito(self):
        cliente = Mock()
        cliente._cliente.get_bucket_cors.return_value = {}
        with patch.object(aplicar_cors, "guardar_respaldo", return_value="/tmp/respaldo"), \
             patch.object(aplicar_cors, "comprobar_options", return_value=[{"aprobado": False}]):
            informe = aplicar_cors.ejecutar(cliente, [ORIGEN_ENSAYO], aplicar=True)
        self.assertTrue(informe["operacion_put_cors_respondio"])
        self.assertFalse(informe["regla_verificada"])
        self.assertFalse(informe["aprobado"])
        cliente._cliente.delete_bucket_cors.assert_not_called()

    def test_consulta_no_escribe(self):
        cliente = Mock()
        cliente._cliente.get_bucket_cors.return_value = {}
        with patch.object(aplicar_cors, "comprobar_options", return_value=[{"aprobado": False}]):
            aplicar_cors.ejecutar(cliente, [ORIGEN_ENSAYO])
        cliente._cliente.put_bucket_cors.assert_not_called()

    def test_respaldo_privado_sin_inventar_reversion(self):
        with tempfile.TemporaryDirectory() as carpeta, \
             patch.object(aplicar_cors.tempfile, "mkdtemp", return_value=carpeta):
            anterior = {"estado": "no_verificable", "CORSRules": None}
            aplicar_cors.guardar_respaldo(anterior, {"CORSRules": []})
            p = Path(carpeta)
            self.assertEqual((p.stat().st_mode & 0o777), 0o700)
            self.assertEqual(((p / "estado-anterior.json").stat().st_mode & 0o777), 0o600)
            self.assertEqual(json.loads((p / "estado-anterior.json").read_text()), anterior)
            self.assertFalse((p / "cors-restaurable.json").exists())
