from rest_framework.test import APITestCase

from subscriptions.tests.helpers import crear_usuario


class CatalogoPlanesTests(APITestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.client.force_authenticate(self.usuario)

    def test_lista_los_tres_planes_del_contrato(self):
        respuesta = self.client.get("/api/v1/planes/")
        self.assertEqual(respuesta.status_code, 200)
        data = respuesta.data["data"]
        self.assertEqual(data["count"], 3)
        self.assertEqual(
            [plan["id"] for plan in data["results"]],
            ["gratuito", "pro", "empresarial"],
        )

    def test_campos_y_formatos_de_cada_plan(self):
        planes = {p["id"]: p for p in self.client.get("/api/v1/planes/").data["data"]["results"]}

        gratuito = planes["gratuito"]
        self.assertEqual(gratuito["precio_mensual"], 0)
        self.assertEqual(gratuito["almacenamiento_bytes"], 16106127360)
        self.assertEqual(gratuito["almacenamiento_legible"], "15 GB")
        self.assertFalse(gratuito["es_popular"])
        self.assertEqual(len(gratuito["caracteristicas"]), 4)

        pro = planes["pro"]
        self.assertEqual(pro["nombre"], "Pro PaaS")
        self.assertEqual(pro["precio_mensual"], 29)
        self.assertEqual(pro["precio_anual"], 278)
        self.assertTrue(pro["es_popular"])

        empresarial = planes["empresarial"]
        self.assertIsNone(empresarial["almacenamiento_bytes"])
        self.assertEqual(empresarial["almacenamiento_legible"], "Ilimitado")

    def test_catalogo_requiere_autenticacion(self):
        self.client.force_authenticate(None)
        respuesta = self.client.get("/api/v1/planes/")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")
