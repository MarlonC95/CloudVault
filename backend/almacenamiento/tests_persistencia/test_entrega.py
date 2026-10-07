"""Cliente fase 9 contra vistas/PG reales; JWT autorizado, negocio y S3 dobles.

No representa integración React ni auth contra la referencia literal. No hace
red, lee .env, borra archivos ni instala fixtures en la base compartida.
"""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from django.db import connection
from django.test import SimpleTestCase
from jsonschema import Draft4Validator, FormatChecker
from rest_framework.test import APIClient

from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.cliente_integracion import CONTENIDO, FalloIntegracion, RespuestaHTTP, recorrer
from almacenamiento.models import IntentoPublicacion, SesionCarga
from almacenamiento.openapi import crear_openapi
from almacenamiento.tests.test_openapi import _json_schema
from .fixtures_aceptacion import ProveedorEnsayo
from .test_inicio import InicioPersistenteTests
from .test_mantenimiento import BucketMantenimiento


class ClienteEntregaPersistenteTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.proveedor = ProveedorEnsayo()
        self.proveedor.sembrar()
        self.bucket = BucketMantenimiento()
        auxiliar = SimpleNamespace(clientes=[])
        self.firmador = InicioPersistenteTests.firmador(auxiliar)
        self.bucket.firmar_descarga = self.firmador.firmar_descarga
        self.client = APIClient()
        self.client.force_authenticate(SimpleNamespace(pk=self.proveedor.actores[0], is_authenticated=True))
        self.api = []
        self.storage = []
        self.exponer_etag = True
        self.fallar_confirmacion = False
        self.corromper_get = False
        for parche in (
            patch("almacenamiento.views.servicios_compartidos", side_effect=lambda: ServiciosCompartidosValidados(self.proveedor)),
            patch("almacenamiento.views.verificador_publicacion", return_value=self.bucket.verificar),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def solicitar(self, metodo, url, *, headers, body=None):
        parsed = urlsplit(url)
        if parsed.hostname == "api.example.invalid":
            self.assertEqual(headers["Authorization"], "Bearer token-sintetico")
            self.assertNotIn("?", parsed.path)
            if "confirmar-carga" in parsed.path and self.fallar_confirmacion:
                return RespuestaHTTP(503, {}, b'{"error":{"code":"SERVICE_UNAVAILABLE","fields":{}}}')
            cliente = self.firmador if "iniciar-carga" in parsed.path else self.bucket
            with patch("almacenamiento.views.cliente_firmador", return_value=cliente):
                respuesta = self.client.generic(metodo, parsed.path, data=body or b"",
                    content_type=headers.get("Content-Type", "application/json"))
            self.api.append((parsed.path, metodo, respuesta.status_code, respuesta.data, dict(respuesta.items())))
            return RespuestaHTTP(respuesta.status_code, dict(respuesta.items()), respuesta.render().content)
        self.assertEqual(parsed.hostname, "bucket-sintetico.s3.example.test")
        self.assertFalse(any(k.lower() == "authorization" for k in headers))
        self.assertIsNone(body if metodo == "GET" else None)
        clave = unquote(parsed.path.lstrip("/"))
        self.storage.append((metodo, headers, body))
        if metodo == "PUT":
            self.assertEqual(headers, {"Content-Type": "text/plain"})
            self.assertEqual(body, CONTENIDO)
            self.bucket.objetos[clave] = (body, headers["Content-Type"])
            return RespuestaHTTP(200, {"ETag": self.bucket.consultar(clave).etag} if self.exponer_etag else {}, b"")
        self.assertEqual(metodo, "GET")
        contenido = self.bucket.objetos[clave][0]
        return RespuestaHTTP(200, {}, b"distinto" if self.corromper_get else contenido)

    def recorrer(self):
        return recorrer(transporte=self, base_api="https://api.example.invalid", token="token-sintetico",
            origen_storage="https://bucket-sintetico.s3.example.test", carpeta_id=str(self.proveedor.carpetas[0]))

    def test_ejemplo_ejecutable_vistas_sql_reserva_uso_y_contrato(self):
        informe = self.recorrer()
        self.assertTrue(informe["aprobado"])
        self.assertEqual(informe["bytes"], 17)
        self.assertEqual(informe["sha256"], hashlib.sha256(CONTENIDO).hexdigest())
        self.assertEqual([r[2] for r in self.api], [201, 200, 200, 200])
        documento = crear_openapi()
        for ruta, metodo, status, body, headers in self.api:
            ruta = ruta.replace(informe["archivo_id"], "{id}")
            response = documento["paths"][ruta][metodo.lower()]["responses"][str(status)]
            Draft4Validator(_json_schema(response["content"]["application/json"]["schema"], documento),
                            format_checker=FormatChecker()).validate(body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(SesionCarga.objects.get().estado, "CONFIRMED")
        self.assertEqual(IntentoPublicacion.objects.get().estado, "PUBLISHED")
        self.assertEqual(self.bucket.copias, 1)
        self.assertEqual(len(self.bucket.objetos), 2)
        self.assertEqual(self.bucket.borrados, [])
        with connection.cursor() as cursor:
            self.assertEqual(cursor.execute("SELECT count(*) FROM archivos").fetchone(), (1,))
            self.assertEqual(cursor.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s",
                [self.proveedor.organizaciones[0]]).fetchone(), (17,))
        self.assertFalse(informe["limpieza_ejecutada"])
        for secreto in ("url_subida", "url_descarga", "X-Amz-Signature", "token-sintetico"):
            self.assertNotIn(secreto, json.dumps(informe))

    def test_etag_no_expuesto_confirma_con_json_vacio(self):
        self.exponer_etag = False
        self.assertTrue(self.recorrer()["aprobado"])
        self.assertEqual(self.bucket.copias, 1)

    def test_confirmacion_falla_conserva_id_sin_reinicio_ni_delete(self):
        self.fallar_confirmacion = True
        with self.assertRaises(FalloIntegracion) as exc:
            self.recorrer()
        self.assertEqual(exc.exception.codigo, "SERVICE_UNAVAILABLE")
        self.assertEqual(exc.exception.informe()["archivo_id"], str(SesionCarga.objects.get().archivo_id))
        self.assertEqual(SesionCarga.objects.count(), 1)
        self.assertEqual(SesionCarga.objects.get().estado, "PENDING")
        self.assertEqual(self.bucket.copias, 0)
        self.assertEqual(self.bucket.borrados, [])

    def test_bytes_get_distintos_no_acreditan_integracion(self):
        self.corromper_get = True
        with self.assertRaises(FalloIntegracion) as exc:
            self.recorrer()
        self.assertEqual(exc.exception.codigo, "CONTENIDO_NO_VERIFICADO")
        self.assertFalse(exc.exception.informe()["aprobado"])

