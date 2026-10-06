import uuid

from django.utils import timezone
from rest_framework.test import APITestCase

from storage.models import FileMetadata
from subscriptions import services
from subscriptions.models import Subscription
from subscriptions.tests.helpers import crear_usuario

GB = 1024 ** 3


class BaseIntegracionTests(APITestCase):
    """Base para integración sin mocks: el consumo se calcula desde FileMetadata reales."""

    def setUp(self):
        self.usuario = crear_usuario()
        self.client.force_authenticate(self.usuario)

    def crear_archivo(self, tamano_bytes, owner=None, en_papelera=False):
        owner = owner or self.usuario
        return FileMetadata.objects.create(
            owner=owner,
            nombre_original="archivo.bin",
            clave_s3=f"clave-{uuid.uuid4().hex}",
            tamano_bytes=tamano_bytes,
            en_papelera=en_papelera,
        )

    def suscribir(self, plan_id, tipo_facturacion="mensual"):
        return self.client.post(
            "/api/v1/mi-plan/suscribir/",
            {"plan_id": plan_id, "tipo_facturacion": tipo_facturacion},
            format="json",
        )


class MiPlanConUsoRealTests(BaseIntegracionTests):
    def test_mi_plan_suma_los_bytes_reales_sin_mocks(self):
        self.crear_archivo(3 * GB)
        self.crear_archivo(2 * GB)

        respuesta = self.client.get("/api/v1/mi-plan/")

        self.assertEqual(respuesta.status_code, 200)
        almacenamiento = respuesta.data["data"]["almacenamiento"]
        self.assertEqual(almacenamiento["usado_bytes"], 5 * GB)
        self.assertEqual(almacenamiento["cuota_bytes"], 15 * GB)
        self.assertEqual(almacenamiento["porcentaje_usado"], 33)

    def test_mi_plan_ignora_los_archivos_de_otros_usuarios(self):
        self.crear_archivo(2 * GB)
        otro = crear_usuario(email="otro@cloudvault.io")
        self.crear_archivo(9 * GB, owner=otro)

        respuesta = self.client.get("/api/v1/mi-plan/")

        self.assertEqual(respuesta.data["data"]["almacenamiento"]["usado_bytes"], 2 * GB)

    def test_mi_plan_cuenta_los_archivos_en_papelera(self):
        self.crear_archivo(4 * GB)
        self.crear_archivo(6 * GB, en_papelera=True)

        respuesta = self.client.get("/api/v1/mi-plan/")

        self.assertEqual(respuesta.data["data"]["almacenamiento"]["usado_bytes"], 10 * GB)


class SuscripcionConCuotaRealTests(BaseIntegracionTests):
    def crear_suscripcion(self, plan_id):
        ahora = timezone.now()
        return Subscription.objects.create(
            usuario=self.usuario,
            plan_id=plan_id,
            tipo_facturacion="mensual",
            periodo_inicio=ahora,
            periodo_fin=services.sumar_meses(ahora, 1),
        )

    def test_downgrade_bloqueado_cuando_el_uso_real_supera_la_cuota(self):
        self.crear_archivo(16 * GB)
        self.crear_suscripcion("pro")

        respuesta = self.suscribir("gratuito")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["error"]["code"], "CUOTA_EXCEDIDA")
        self.assertIn("plan_id", respuesta.data["error"]["fields"])
        self.assertEqual(Subscription.objects.get(usuario=self.usuario).plan_id, "pro")

    def test_cambio_permitido_cuando_el_uso_real_cabe_en_la_nueva_cuota(self):
        self.crear_archivo(10 * GB)
        self.crear_suscripcion("pro")

        respuesta = self.suscribir("gratuito")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Subscription.objects.get(usuario=self.usuario).plan_id, "gratuito")

    def test_upgrade_permitido_con_uso_real_alto(self):
        self.crear_archivo(50 * GB)

        respuesta = self.suscribir("pro")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Subscription.objects.get(usuario=self.usuario).plan_id, "pro")
