"""Pruebas del contrato interno de cuotas consumido por el Run 4."""

from datetime import datetime, timedelta

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from common.testing import (
    PLAN_GRATUITO, crear_organizacion, crear_suscripcion, espacio_de_trabajo,
)
from subscriptions.cuotas import SinSuscripcionVigente, leer_cuota_organizacion

GB = 1024 ** 3


class LeerCuotaOrganizacionTests(TestCase):
    def test_devuelve_limite_usado_y_periodo(self):
        _, organizacion_id = espacio_de_trabajo()
        limite, usado, periodo_fin = leer_cuota_organizacion(organizacion_id)
        self.assertEqual(limite, 15 * GB)
        self.assertEqual(usado, 0)
        self.assertIsInstance(periodo_fin, datetime)
        self.assertGreater(periodo_fin, timezone.now())

    def test_sin_suscripcion_falla_con_error_claro(self):
        organizacion_id = crear_organizacion()
        with self.assertRaises(SinSuscripcionVigente):
            leer_cuota_organizacion(organizacion_id)

    def test_suscripcion_cancelada_no_cuenta(self):
        organizacion_id = crear_organizacion()
        crear_suscripcion(organizacion_id, plan_id=PLAN_GRATUITO, estado="CANCELED")
        with self.assertRaises(SinSuscripcionVigente):
            leer_cuota_organizacion(organizacion_id)

    def test_suscripcion_vencida_no_cuenta(self):
        organizacion_id = crear_organizacion()
        crear_suscripcion(organizacion_id, plan_id=PLAN_GRATUITO, dias=-1)
        with self.assertRaises(SinSuscripcionVigente):
            leer_cuota_organizacion(organizacion_id)

    def test_plan_inactivo_no_cuenta(self):
        _, organizacion_id = espacio_de_trabajo()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE planes SET esta_activo = FALSE WHERE id = %s", [PLAN_GRATUITO])
        with self.assertRaises(SinSuscripcionVigente):
            leer_cuota_organizacion(organizacion_id)

    def test_limite_se_actualiza_con_el_plan(self):
        _, organizacion_id = espacio_de_trabajo()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE suscripciones SET plan_id = 3
                   WHERE organizacion_id = %s AND estado = 'ACTIVE'""",
                [organizacion_id],
            )
            cursor.execute(
                "UPDATE organizaciones SET almacenamiento_usado_bytes = %s WHERE id = %s",
                [7 * GB, organizacion_id],
            )
        limite, usado, _ = leer_cuota_organizacion(organizacion_id)
        self.assertEqual(limite, 1099511627776)
        self.assertEqual(usado, 7 * GB)

    def test_vigencia_estricta_del_periodo(self):
        organizacion_id = crear_organizacion()
        ahora = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO suscripciones
                   (organizacion_id, plan_id, estado, intervalo, periodo_inicio, periodo_fin)
                   VALUES (%s, %s, 'ACTIVE', 'MONTHLY', %s, %s)""",
                [organizacion_id, PLAN_GRATUITO, ahora - timedelta(days=1), ahora],
            )
        with self.assertRaises(SinSuscripcionVigente):
            leer_cuota_organizacion(organizacion_id)
