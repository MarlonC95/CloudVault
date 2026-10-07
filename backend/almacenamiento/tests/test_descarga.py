"""HTTP y firmas SigV4 reales offline; sin DB, .env ni sockets."""

from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from almacenamiento.configuracion_descarga import vigencia_descarga
from almacenamiento.descarga import ServicioDescargas
from almacenamiento.errores import ErrorCarga
from almacenamiento.s3 import ClienteS3, ErrorS3, disposicion_adjunto, nueva_clave_final, nueva_clave_temporal
from .test_s3 import configuracion


class DescargaHTTPTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=uuid4(), is_authenticated=True)
        self.id = str(uuid4())
        self.ruta = f"/api/v1/archivos/{self.id}/descarga/"
        self.cliente = APIClient()

    def test_jwt_ausente_invalido_y_vencido_no_llaman_dependencias(self):
        vencido = AccessToken()
        vencido["exp"] = 1
        for token in (None, "synthetic-invalid", str(vencido)):
            self.cliente.credentials(**({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}))
            with patch("almacenamiento.views.servicios_compartidos") as proveedor:
                respuesta = self.cliente.get(self.ruta)
            self.assertEqual(respuesta.status_code, 401)
            self.assertEqual(respuesta["WWW-Authenticate"], "Bearer")
            self.assertEqual(respuesta["Cache-Control"], "no-store")
            proveedor.assert_not_called()

    @override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_proveedor_ausente_503_sin_sql_s3_o_firma(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.cliente_firmador") as sdk:
            respuesta = self.cliente.get(self.ruta)
        self.assertEqual(respuesta.status_code, 503)
        sdk.assert_not_called()

    def test_jwt_firmado_existente_usuario_lookup_sustituido(self):
        token = AccessToken()
        token["user_id"] = str(self.actor.pk)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=""), \
             patch("auth_workspaces.authentication.CloudVaultJWTAuthentication.get_user", return_value=self.actor) as lookup:
            self.assertEqual(self.cliente.get(self.ruta).status_code, 503)
        lookup.assert_called_once()

    def test_id_y_actor_invalidos_antes_de_proveedor(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.servicios_compartidos") as proveedor:
            self.assertEqual(self.cliente.get(self.ruta.replace(self.id, "sin-uuid")).status_code, 400)
            self.actor.pk = 123
            self.assertEqual(self.cliente.get(self.ruta).status_code, 401)
            proveedor.assert_not_called()

    def test_query_body_y_metodos_no_aceptados(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.servicios_compartidos") as proveedor:
            for query in ("?key=ajena", "?bucket=otro", "?vigencia=999", "?nombre=otro.txt"):
                self.assertEqual(self.cliente.get(self.ruta+query).status_code, 400)
            for body in ('{"clave":"ajena"}', 'x' * 20000):
                self.assertEqual(self.cliente.generic("GET", self.ruta, data=body,
                                                       content_type="application/json").status_code, 400)
            self.assertEqual(self.cliente.post(self.ruta, {}, format="json").status_code, 405)
            self.assertEqual(self.cliente.head(self.ruta).status_code, 405)
            proveedor.assert_not_called()

    def test_respuesta_200_contrato_cache_y_parametros_del_servicio(self):
        self.cliente.force_authenticate(self.actor)
        salida = {"data": {"url_descarga": "https://example.test/final?firma=synthetic",
                            "nombre": "documento.txt", "expira_en": "2030-01-01T00:00:00Z"}}
        with patch("almacenamiento.views.ServicioDescargas") as servicio:
            servicio.return_value.descargar.return_value = salida
            respuesta = self.cliente.get(self.ruta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, salida)
        servicio.return_value.descargar.assert_called_once_with(solicitante_id=self.actor.pk, archivo_id=self.id)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertEqual(respuesta["Referrer-Policy"], "no-referrer")

    def test_error_privado_no_sale_en_respuesta_o_logs(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.ServicioDescargas") as servicio, \
             self.assertLogs("almacenamiento.errores", level="ERROR") as logs:
            servicio.return_value.descargar.side_effect = RuntimeError("synthetic-private-url")
            respuesta = self.cliente.get(self.ruta)
        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn("synthetic-private-url", str(respuesta.data) + str(logs.output))

    def test_ttl_configurable_y_configuracion_invalida(self):
        with override_settings(ALMACENAMIENTO_VIGENCIA_DESCARGA_SEGUNDOS="30"):
            self.assertEqual(vigencia_descarga(), 30)
        for valor in (True, 0, -1, 301, "nan"):
            with override_settings(ALMACENAMIENTO_VIGENCIA_DESCARGA_SEGUNDOS=valor), self.assertRaises(ErrorCarga):
                vigencia_descarga()


class FirmaDescargaTests(SimpleTestCase):
    def setUp(self):
        self.cliente = ClienteS3(configuracion())
        self.addCleanup(self.cliente.cerrar)
        self.final = nueva_clave_final(uuid4())

    def test_sigv4_get_adjunto_tipo_seguro_no_cache_y_ttl(self):
        firma = self.cliente.firmar_descarga(self.final, "informe.html", vigencia=30)
        query = parse_qs(urlsplit(firma.url).query)
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertEqual(query["X-Amz-Expires"], ["30"])
        self.assertEqual(query["response-content-type"], ["application/octet-stream"])
        self.assertEqual(query["response-cache-control"], ["private, no-store"])
        self.assertTrue(query["response-content-disposition"][0].startswith("attachment;"))
        self.assertEqual(urlsplit(firma.url).path, "/"+self.final)
        self.assertEqual(firma.metodo, "GET")
        self.assertEqual(firma.encabezados, {})
        self.assertNotIn(firma.url, repr(firma))

    def test_nombre_unicode_comillas_punto_y_coma_percent_encoded(self):
        nombre = 'informe "abril"; español ✅.pdf'
        header = disposicion_adjunto(nombre)
        self.assertTrue(header.isascii())
        self.assertNotIn('"abril";', header)
        self.assertEqual(unquote(header.split("filename*=UTF-8''", 1)[1]), nombre)
        url = self.cliente.firmar_descarga(self.final, nombre).url
        self.assertEqual(parse_qs(urlsplit(url).query)["response-content-disposition"], [header])

    def test_rechaza_controles_paths_surrogates_y_temporales(self):
        for nombre in ("x\r\nInjected: yes.txt", "../otro.txt", "a\\b.txt", "..", "x\x00.txt", "x\ud800.txt"):
            with self.subTest(nombre_tipo="malicioso"), self.assertRaises(ValueError):
                self.cliente.firmar_descarga(self.final, nombre)
        for clave in (nueva_clave_temporal(), "archivos/documento.pdf"):
            with self.assertRaises(ValueError):
                self.cliente.firmar_descarga(clave, "documento.txt")

    def test_version_opcional_y_fallback_unicode_sin_ascii(self):
        firma = self.cliente.firmar_descarga(self.final, "中文.pdf", version="version-sintetica")
        self.assertEqual(parse_qs(urlsplit(firma.url).query)["versionId"], ["version-sintetica"])
        self.assertIn('filename="archivo"', disposicion_adjunto("中文"))

    def test_ttl_no_ampliable_o_booleano(self):
        for ttl in (0, True, 301, "300"):
            with self.assertRaises(ValueError):
                self.cliente.firmar_descarga(self.final, "documento.txt", vigencia=ttl)

    def test_fecha_coincide_exactamente_con_firma_y_sdk_incompleto_no_se_acepta(self):
        firma = self.cliente.firmar_descarga(self.final, "documento.txt", vigencia=30)
        query = parse_qs(urlsplit(firma.url).query)
        firmado = datetime.strptime(query["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        self.assertEqual(firma.expira_en, firmado+timedelta(seconds=30))
        with patch.object(self.cliente._firmador, "generate_presigned_url", return_value="https://example.test/synthetic"), self.assertRaises(ErrorS3):
            self.cliente.firmar_descarga(self.final, "documento.txt")

    def test_limites_del_servicio(self):
        for kwargs in ({"vigencia": 301}, {"limite": 0}, {"ventana_segundos": True}):
            with self.assertRaises(ValueError):
                ServicioDescargas(servicios_factory=lambda: None, cliente_factory=lambda: None, **kwargs)
