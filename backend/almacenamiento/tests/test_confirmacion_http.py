"""Frontera HTTP de confirmación sin DB, .env ni red."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from almacenamiento.configuracion_inicio import maximo_publicacion, verificador_publicacion
from almacenamiento.errores import ErrorCarga


class ConfirmacionHTTPTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=uuid4(), is_authenticated=True)
        self.cliente = APIClient()
        self.id = str(uuid4())
        self.ruta = f"/api/v1/archivos/{self.id}/confirmar-carga/"

    def test_jwt_ausente_e_invalido_no_consultan_proveedor(self):
        for token in (None, "synthetic-invalid"):
            if token:
                self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            with patch("almacenamiento.views.servicios_compartidos") as proveedor:
                respuesta = self.cliente.post(self.ruta, {}, format="json")
            self.assertEqual(respuesta.status_code, 401)
            proveedor.assert_not_called()

    @override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_proveedor_ausente_no_consulta_sql_s3_o_worker(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.cliente_firmador") as cliente, \
             patch("almacenamiento.verificacion.subprocess.run") as worker:
            respuesta = self.cliente.post(self.ruta, {}, format="json")
        self.assertEqual(respuesta.status_code, 503)
        cliente.assert_not_called()
        worker.assert_not_called()

    def test_id_body_etag_y_actor_invalidos_se_rechazan_antes_del_proveedor(self):
        self.cliente.force_authenticate(self.actor)
        casos = ((self.ruta.replace(self.id, "sin-uuid"), {}),
                 (self.ruta, {"etag": True}), (self.ruta, {"etag": "x\ny"}),
                 (self.ruta, {"checksum_sha256": "a" * 64}), (self.ruta, []))
        for ruta, body in casos:
            with self.subTest(body=body), patch("almacenamiento.views.servicios_compartidos") as proveedor:
                respuesta = self.cliente.post(ruta, body, format="json")
                self.assertEqual(respuesta.status_code, 400)
                proveedor.assert_not_called()
        self.actor.pk = 42
        with patch("almacenamiento.views.servicios_compartidos") as proveedor:
            respuesta = self.cliente.post(self.ruta, {}, format="json")
        self.assertEqual(respuesta.status_code, 401)
        proveedor.assert_not_called()

    def test_body_vacio_etag_opcional_y_200_sin_cache(self):
        self.cliente.force_authenticate(self.actor)
        resultado = {"data": {"id": self.id, "nombre": "ensayo.txt", "es_nuevo": True,
                               "en_papelera": False}}
        for body in ({}, {"etag": '"pista"'}, None):
            with patch("almacenamiento.views.ServicioConfirmacionCargas") as servicio:
                servicio.return_value.confirmar.return_value = resultado
                respuesta = (self.cliente.post(self.ruta) if body is None else
                             self.cliente.post(self.ruta, body, format="json"))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.data, resultado)
                servicio.return_value.confirmar.assert_called_once_with(
                    solicitante_id=self.actor.pk, archivo_id=self.id, datos=body or {})
                self.assertEqual(respuesta["Cache-Control"], "no-store")
                self.assertEqual(respuesta["Referrer-Policy"], "no-referrer")

    def test_metodo_y_body_pesado_binario_malformado(self):
        self.cliente.force_authenticate(self.actor)
        self.assertEqual(self.cliente.get(self.ruta).status_code, 405)
        for body, tipo in (("{", "application/json"), ("bytes", "application/octet-stream"),
                           ('{"etag":"' + 'x' * 17000 + '"}', "application/json")):
            with patch("almacenamiento.views.servicios_compartidos") as proveedor:
                self.assertEqual(self.cliente.post(self.ruta, body, content_type=tipo).status_code, 400)
                proveedor.assert_not_called()

    def test_error_no_expone_excepcion_privada(self):
        self.cliente.force_authenticate(self.actor)
        with patch("almacenamiento.views.ServicioConfirmacionCargas") as servicio, \
             self.assertLogs("almacenamiento.errores", level="ERROR") as logs:
            servicio.return_value.confirmar.side_effect = RuntimeError("synthetic-private-value")
            respuesta = self.cliente.post(self.ruta, {}, format="json")
        self.assertEqual(respuesta.status_code, 500)
        self.assertNotIn("synthetic-private-value", str(respuesta.data) + str(logs.output))

    def test_configuracion_acotada(self):
        self.assertEqual(maximo_publicacion(), 1 << 30)
        self.assertEqual(verificador_publicacion().tiempo_maximo, 60)
        for nombre, valor in (("ALMACENAMIENTO_MAXIMO_PUBLICACION_BYTES", 6 << 30),
                              ("ALMACENAMIENTO_VERIFICACION_SEGUNDOS", 301)):
            with override_settings(**{nombre: valor}), self.assertRaises(ErrorCarga):
                maximo_publicacion() if "BYTES" in nombre else verificador_publicacion()
