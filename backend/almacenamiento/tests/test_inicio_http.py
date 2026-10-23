"""HTTP, JWT y configuración sin SQL/red; servicio exitoso sustituido explícitamente."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from almacenamiento.configuracion_inicio import entero_configurado, politica_inicio, servicios_compartidos
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga


RUTA = "/api/v1/archivos/iniciar-carga/"
DATOS = {"nombre": "ensayo.txt", "tamano_bytes": 50, "tipo_mime": "text/plain"}


class InicioHTTPTests(SimpleTestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.usuario = SimpleNamespace(pk=uuid4(), is_authenticated=True)

    def autenticar(self):
        self.cliente.force_authenticate(self.usuario)

    def test_sin_jwt_no_llama_dependencias(self):
        with patch("almacenamiento.views.servicios_compartidos") as servicios:
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")
        self.assertEqual(respuesta["WWW-Authenticate"], "Bearer")
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        servicios.assert_not_called()

    def test_jwt_invalido_no_llama_dependencias(self):
        vencido = AccessToken()
        vencido["exp"] = 1
        for token in ("synthetic-invalid-token", str(vencido)):
            with self.subTest(token_tipo="vencido" if token == str(vencido) else "invalido"):
                self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
                with patch("almacenamiento.views.servicios_compartidos") as servicios:
                    respuesta = self.cliente.post(RUTA, DATOS, format="json")
                self.assertEqual(respuesta.status_code, 401)
                self.assertEqual(respuesta.data["error"]["code"], "TOKEN_INVALIDO")
                servicios.assert_not_called()

    def test_solo_post_y_actor_uuid(self):
        self.autenticar()
        respuesta = self.cliente.get(RUTA)
        self.assertEqual(respuesta.status_code, 405)
        self.usuario.pk = 123
        with patch("almacenamiento.views.servicios_compartidos") as servicios:
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 401)
        servicios.assert_not_called()

    def test_jwt_firmado_valido_usa_autenticacion_existente(self):
        token = AccessToken()
        token["user_id"] = str(self.usuario.pk)
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with patch("auth_workspaces.authentication.CloudVaultJWTAuthentication.get_user",
                   return_value=self.usuario) as usuario, \
             patch("almacenamiento.views.servicios_compartidos",
                   side_effect=ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)):
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 503)
        usuario.assert_called_once()

    @override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_proveedor_ausente_no_firma_ni_toca_sql(self):
        self.autenticar()
        with patch("almacenamiento.views.cliente_firmador") as firmador:
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.data["error"]["code"], "SERVICE_UNAVAILABLE")
        firmador.assert_not_called()

    def test_input_invalido_no_consulta_servicios(self):
        self.autenticar()
        for datos in ({**DATOS, "tamano_bytes": True}, {**DATOS, "bucket": "otro"},
                      {**DATOS, "nombre": "../ensayo.txt"}, {**DATOS, "tamano_bytes": -1}, []):
            with self.subTest(datos=datos), patch("almacenamiento.views.servicios_compartidos") as servicios:
                respuesta = self.cliente.post(RUTA, datos, format="json")
                self.assertEqual(respuesta.status_code, 400)
                servicios.assert_not_called()

    def test_json_roto_binario_y_json_pesado_se_rechazan(self):
        self.autenticar()
        for body, tipo in (("{", "application/json"), ("bytes", "application/octet-stream"),
                           ('{"nombre":"' + 'x' * 17000 + '"}', "application/json")):
            with self.subTest(tipo=tipo), patch("almacenamiento.views.servicios_compartidos") as servicios:
                respuesta = self.cliente.post(RUTA, body, content_type=tipo)
                self.assertEqual(respuesta.status_code, 400)
                servicios.assert_not_called()

    def test_salida_http_201_y_no_cache(self):
        self.autenticar()
        salida = {"data": {"archivo_id": str(uuid4()), "url_subida": "https://example.test/synthetic",
                           "metodo": "PUT", "encabezados": {"Content-Type": "text/plain"},
                           "expira_en": "2030-01-01T00:00:00Z"}}
        with patch("almacenamiento.views.ServicioInicioCargas") as servicio:
            servicio.return_value.iniciar.return_value = salida
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data, salida)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertEqual(respuesta["Referrer-Policy"], "no-referrer")

    def test_error_interno_no_imprime_datos_privados(self):
        self.autenticar()
        secreto = "synthetic-private-url-and-password"
        with patch("almacenamiento.views.ServicioInicioCargas") as servicio, \
             self.assertLogs("almacenamiento.errores", level="ERROR") as logs:
            servicio.return_value.iniciar.side_effect = RuntimeError(secreto)
            respuesta = self.cliente.post(RUTA, DATOS, format="json")
        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn(secreto, str(respuesta.data) + str(logs.output))


class ConfiguracionInicioTests(SimpleTestCase):
    @override_settings(ALMACENAMIENTO_MAXIMO_ARCHIVO_BYTES="1024",
                       ALMACENAMIENTO_VIGENCIA_CARGA_SEGUNDOS="30")
    def test_politica_de_ambiente(self):
        politica = politica_inicio()
        self.assertEqual(politica.maximo_archivo_bytes, 1024)
        self.assertEqual(politica.vigencia_carga_segundos, 30)

    def test_configuracion_invalida_falla_cerrada(self):
        for valor in (True, 0, -1, "nan", "-10", "1.5"):
            with self.subTest(valor=valor), override_settings(ALMACENAMIENTO_INICIOS_POR_VENTANA=valor):
                with self.assertRaises(ErrorCarga):
                    entero_configurado("ALMACENAMIENTO_INICIOS_POR_VENTANA", 10)
        with override_settings(ALMACENAMIENTO_VIGENCIA_CARGA_SEGUNDOS=901), self.assertRaises(ErrorCarga):
            politica_inicio()

    def test_fabrica_incompatible_no_se_reemplaza_por_mock(self):
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="no_existe.proveedor"), self.assertRaises(ErrorCarga):
            servicios_compartidos()
        fabrica = Mock(return_value=SimpleNamespace(using="otra_base"))
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=fabrica), self.assertRaises(ErrorCarga):
            servicios_compartidos()
