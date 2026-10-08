"""§10.1 — Catálogo de planes sobre el seed SQL real."""

from django.test import TestCase
from rest_framework.test import APIClient

from common.testing import cliente_autenticado, espacio_de_trabajo

GB = 1024 ** 3
URL = "/api/v1/planes/"


class CatalogoPlanesTests(TestCase):
    def setUp(self):
        usuario_id, _ = espacio_de_trabajo()
        self.client = cliente_autenticado(usuario_id)

    def test_lista_los_tres_planes_del_contrato_ordenados_por_id(self):
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        data = respuesta.data["data"]
        self.assertEqual(data["count"], 3)
        self.assertEqual(
            [plan["id"] for plan in data["results"]],
            ["gratuito", "pro", "empresarial"],
        )

    def test_campos_y_formatos_de_cada_plan(self):
        planes = {p["id"]: p for p in self.client.get(URL).data["data"]["results"]}

        gratuito = planes["gratuito"]
        self.assertEqual(gratuito["nombre"], "Gratuito")
        self.assertEqual(gratuito["precio_mensual"], 0)
        self.assertEqual(gratuito["precio_anual"], 0)
        self.assertEqual(gratuito["almacenamiento_bytes"], 15 * GB)
        self.assertEqual(gratuito["almacenamiento_legible"], "15 GB")
        self.assertFalse(gratuito["es_popular"])
        self.assertEqual(len(gratuito["caracteristicas"]), 4)

        pro = planes["pro"]
        self.assertEqual(pro["nombre"], "Pro PaaS")
        self.assertEqual(pro["precio_mensual"], 29)
        self.assertEqual(pro["precio_anual"], 278)
        self.assertEqual(pro["almacenamiento_legible"], "100 GB")
        self.assertTrue(pro["es_popular"])

        empresarial = planes["empresarial"]
        self.assertEqual(empresarial["nombre"], "Empresarial")
        self.assertEqual(empresarial["precio_mensual"], 99)
        self.assertEqual(empresarial["precio_anual"], 950)
        self.assertEqual(empresarial["almacenamiento_bytes"], 1099511627776)
        self.assertEqual(empresarial["almacenamiento_legible"], "1 TB")
        self.assertFalse(empresarial["es_popular"])
        self.assertTrue(
            any("1 TB" in caracteristica for caracteristica in empresarial["caracteristicas"])
        )
        self.assertFalse(
            any("ilimitado" in c.lower() for c in empresarial["caracteristicas"][:1])
        )

    def test_catalogo_requiere_autenticacion(self):
        respuesta = APIClient().get(URL)
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")
