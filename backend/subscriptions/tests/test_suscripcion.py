"""§10.2/§10.3 — Consulta y cambio de plan por organización."""

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from common.testing import (
    agregar_miembro, cliente_autenticado, crear_organizacion, crear_usuario,
    espacio_de_trabajo,
)
from subscriptions import services
from subscriptions.models import HistorialPago, Suscripcion

GB = 1024 ** 3
MI_PLAN = "/api/v1/mi-plan/"
SUSCRIBIR = "/api/v1/mi-plan/suscribir/"
FACTURAS = "/api/v1/mi-plan/facturas/"


def fijar_uso(organizacion_id, usado_bytes):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE organizaciones SET almacenamiento_usado_bytes = %s WHERE id = %s",
            [usado_bytes, organizacion_id],
        )


class MiPlanTests(TestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def test_devuelve_plan_estado_y_cuota(self):
        respuesta = self.client.get(MI_PLAN)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        data = respuesta.data["data"]
        self.assertEqual(data["plan"]["id"], "gratuito")
        self.assertEqual(data["plan"]["nombre"], "Gratuito")
        self.assertEqual(data["plan"]["tipo_facturacion"], "mensual")
        self.assertEqual(data["estado"], "ACTIVE")
        self.assertEqual(data["almacenamiento"]["cuota_bytes"], 15 * GB)
        self.assertIsNotNone(data["renueva_en"])

    def test_refleja_el_consumo_de_la_organizacion(self):
        fijar_uso(self.organizacion_id, 45 * GB)
        almacenamiento = self.client.get(MI_PLAN).data["data"]["almacenamiento"]
        self.assertEqual(almacenamiento["usado_bytes"], 45 * GB)
        self.assertEqual(almacenamiento["cuota_bytes"], 15 * GB)
        self.assertEqual(almacenamiento["porcentaje_usado"], 300)

    def test_organizacion_ajena_es_404(self):
        ajena = crear_organizacion()
        respuesta = self.client.get(MI_PLAN, {"organizacion_id": str(ajena)})
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.data["error"]["code"], "NO_ENCONTRADO")

    def test_sin_suscripcion_vigente_es_409(self):
        usuario_id = crear_usuario()
        organizacion_id = crear_organizacion()
        agregar_miembro(organizacion_id, usuario_id, 0)
        respuesta = cliente_autenticado(usuario_id).get(MI_PLAN)
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["error"]["code"], "CONTEXT_NOT_READY")

    def test_mi_plan_requiere_autenticacion(self):
        respuesta = APIClient().get(MI_PLAN)
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")


class SuscribirTests(TestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def suscribir(self, plan_id, tipo_facturacion="mensual"):
        return self.client.post(
            SUSCRIBIR,
            {"plan_id": plan_id, "tipo_facturacion": tipo_facturacion},
            format="json",
        )

    def test_suscribir_mensual_actualiza_la_suscripcion(self):
        respuesta = self.suscribir("pro", "mensual")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        data = respuesta.data["data"]
        self.assertEqual(data["plan"]["id"], "pro")
        self.assertEqual(data["plan"]["tipo_facturacion"], "mensual")
        self.assertEqual(data["estado"], "ACTIVE")

        suscripcion = Suscripcion.objects.get(organizacion_id=self.organizacion_id)
        self.assertEqual(suscripcion.plan_id, 2)
        self.assertEqual(suscripcion.estado, "ACTIVE")
        self.assertEqual(suscripcion.intervalo, "MONTHLY")
        self.assertEqual(
            suscripcion.periodo_fin,
            services.sumar_meses(suscripcion.periodo_inicio, 1),
        )

    def test_suscribir_anual_renueva_en_un_anio(self):
        respuesta = self.suscribir("empresarial", "anual")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        suscripcion = Suscripcion.objects.get(organizacion_id=self.organizacion_id)
        self.assertEqual(suscripcion.plan_id, 3)
        self.assertEqual(suscripcion.intervalo, "YEARLY")
        self.assertEqual(
            suscripcion.periodo_fin,
            services.sumar_meses(suscripcion.periodo_inicio, 12),
        )

    def test_validacion_de_plan_y_tipo_facturacion(self):
        respuesta = self.suscribir("inexistente", "semanal")
        self.assertEqual(respuesta.status_code, 400)
        error = respuesta.data["error"]
        self.assertEqual(error["code"], "VALIDATION_ERROR")
        self.assertIn("plan_id", error["fields"])
        self.assertIn("tipo_facturacion", error["fields"])
        self.assertEqual(
            Suscripcion.objects.get(organizacion_id=self.organizacion_id).plan_id, 1
        )

    def test_downgrade_bloqueado_por_cuota(self):
        self.suscribir("pro")
        fijar_uso(self.organizacion_id, 16 * GB)
        respuesta = self.suscribir("gratuito")
        self.assertEqual(respuesta.status_code, 409)
        error = respuesta.data["error"]
        self.assertEqual(error["code"], "CUOTA_EXCEDIDA")
        self.assertIn("plan_id", error["fields"])
        self.assertEqual(
            Suscripcion.objects.get(organizacion_id=self.organizacion_id).plan_id, 2
        )

    def test_upgrade_permitido_con_uso_alto(self):
        fijar_uso(self.organizacion_id, 50 * GB)
        respuesta = self.suscribir("pro")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(
            Suscripcion.objects.get(organizacion_id=self.organizacion_id).plan_id, 2
        )

    def test_solo_propietario_suscribe(self):
        usuario_id, organizacion_id = espacio_de_trabajo(nivel_rol=2)
        respuesta = cliente_autenticado(usuario_id).post(
            SUSCRIBIR,
            {"plan_id": "pro", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.data["error"]["code"], "SIN_PERMISO")
        self.assertEqual(
            Suscripcion.objects.get(organizacion_id=organizacion_id).plan_id, 1
        )

    def test_suscribir_requiere_autenticacion(self):
        respuesta = APIClient().post(
            SUSCRIBIR,
            {"plan_id": "pro", "tipo_facturacion": "mensual"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")

    def test_suscribir_registra_pago_simulado(self):
        respuesta = self.suscribir("pro", "mensual")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        suscripcion = Suscripcion.objects.get(organizacion_id=self.organizacion_id)
        self.assertEqual(HistorialPago.objects.filter(suscripcion=suscripcion).count(), 1)
        pago = HistorialPago.objects.get()
        self.assertEqual(pago.estado, "COMPLETED")
        self.assertEqual(int(pago.monto), 29)

    def test_suscribir_anual_registra_monto_anual(self):
        respuesta = self.suscribir("pro", "anual")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        pago = HistorialPago.objects.get()
        self.assertEqual(int(pago.monto), services.precio_anual(29))


class FacturasTests(TestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def test_facturas_requiere_autenticacion(self):
        respuesta = APIClient().get(FACTURAS)
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")

    def test_facturas_lista_pagos_de_la_suscripcion(self):
        self.client.post(SUSCRIBIR, {"plan_id": "pro", "tipo_facturacion": "mensual"}, format="json")
        respuesta = self.client.get(FACTURAS)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        data = respuesta.data["data"]
        self.assertEqual(data["count"], 1)
        factura = data["results"][0]
        self.assertEqual(factura["monto"], 29)
        self.assertEqual(factura["moneda"], "USD")
        self.assertEqual(factura["estado"], "pagada")
        self.assertTrue(factura["url_pdf"].startswith("https://cloudvault.app/facturas/"))
