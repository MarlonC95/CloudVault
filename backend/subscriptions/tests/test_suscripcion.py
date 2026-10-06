from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from subscriptions import services
from subscriptions.models import Subscription
from subscriptions.tests.helpers import crear_usuario

GB = 1024 ** 3


class MiPlanTests(APITestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.client.force_authenticate(self.usuario)

    @patch("subscriptions.views.get_used_bytes", return_value=0)
    def test_sin_suscripcion_crea_el_plan_gratuito(self, _usado):
        respuesta = self.client.get("/api/v1/mi-plan/")
        self.assertEqual(respuesta.status_code, 200)
        data = respuesta.data["data"]
        self.assertEqual(data["plan"]["id"], "gratuito")
        self.assertEqual(data["estado"], "activo")
        self.assertEqual(data["plan"]["tipo_facturacion"], "mensual")
        self.assertEqual(data["almacenamiento"]["cuota_bytes"], 15 * GB)
        self.assertTrue(Subscription.objects.filter(usuario=self.usuario).exists())

    @patch("subscriptions.views.get_used_bytes", return_value=45 * GB)
    def test_devuelve_consumo_y_renovacion(self, _usado):
        respuesta = self.client.get("/api/v1/mi-plan/")
        almacenamiento = respuesta.data["data"]["almacenamiento"]
        self.assertEqual(almacenamiento["usado_bytes"], 45 * GB)
        self.assertEqual(almacenamiento["cuota_bytes"], 15 * GB)
        self.assertEqual(almacenamiento["porcentaje_usado"], 300)
        self.assertIsNotNone(respuesta.data["data"]["renueva_en"])

    def test_mi_plan_requiere_autenticacion(self):
        self.client.force_authenticate(None)
        respuesta = self.client.get("/api/v1/mi-plan/")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")


class SuscribirTests(APITestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.client.force_authenticate(self.usuario)

    @patch("subscriptions.views.get_used_bytes", return_value=0)
    def test_suscribir_mensual_crea_suscripcion(self, _usado):
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "pro", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        data = respuesta.data["data"]
        self.assertEqual(data["plan"]["id"], "pro")
        self.assertEqual(data["plan"]["tipo_facturacion"], "mensual")
        self.assertEqual(data["estado"], "activo")

        suscripcion = Subscription.objects.get(usuario=self.usuario)
        self.assertEqual(suscripcion.plan_id, "pro")
        esperado = services.sumar_meses(suscripcion.periodo_inicio, 1)
        self.assertEqual(suscripcion.periodo_fin, esperado)

    @patch("subscriptions.views.get_used_bytes", return_value=0)
    def test_suscribir_anual_renueva_en_un_anio(self, _usado):
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "empresarial", "tipo_facturacion": "anual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        suscripcion = Subscription.objects.get(usuario=self.usuario)
        esperado = services.sumar_meses(suscripcion.periodo_inicio, 12)
        self.assertEqual(suscripcion.periodo_fin, esperado)

    @patch("subscriptions.views.get_used_bytes", return_value=0)
    def test_validacion_de_plan_y_tipo_facturacion(self, _usado):
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "inexistente", "tipo_facturacion": "semanal"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        error = respuesta.data["error"]
        self.assertEqual(error["code"], "VALIDATION_ERROR")
        self.assertIn("plan_id", error["fields"])
        self.assertIn("tipo_facturacion", error["fields"])
        self.assertFalse(Subscription.objects.filter(usuario=self.usuario).exists())

    @patch("subscriptions.views.get_used_bytes", return_value=50 * GB)
    def test_downgrade_bloqueado_por_cuota(self, _usado):
        ahora = timezone.now()
        Subscription.objects.create(
            usuario=self.usuario,
            plan_id="pro",
            tipo_facturacion="mensual",
            periodo_inicio=ahora,
            periodo_fin=services.sumar_meses(ahora, 1),
        )
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "gratuito", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409)
        error = respuesta.data["error"]
        self.assertEqual(error["code"], "CUOTA_EXCEDIDA")
        self.assertIn("plan_id", error["fields"])
        self.assertEqual(Subscription.objects.get(usuario=self.usuario).plan_id, "pro")

    @patch("subscriptions.views.get_used_bytes", return_value=0)
    def test_empresarial_ilimitado_no_bloquea(self, _usado):
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "empresarial", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_suscribir_requiere_autenticacion(self):
        self.client.force_authenticate(None)
        respuesta = self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": "pro", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")
