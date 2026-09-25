"""Contract tests against an isolated PostgreSQL database."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import IntegrityError, OperationalError, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from auth_workspaces.models import LogAuditoria, Usuario
from auth_workspaces.services import registrar_usuario


URL = "/api/v1/auth/registro/"


def payload(correo="Ana.Perez@Ejemplo.com"):
    return {
        "nombre_completo": "Ana Pérez",
        "correo_electronico": correo,
        "contrasena": "UnaFraseSeguraPara2026",
        "palabra_secreta": "Recuerdo privado de hace años",
    }


class RegistroTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_registro_crea_identidad_hashes_y_auditoria(self):
        response = self.client.post(URL, payload(), format="json", REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Usuario.objects.count(), 1)
        user = Usuario.objects.get()
        self.assertEqual(user.correo_electronico, "ana.perez@ejemplo.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_2fa_enabled)
        self.assertTrue(user.check_password(payload()["contrasena"]))
        self.assertTrue(check_password(payload()["palabra_secreta"], user.palabra_secreta_hash))
        self.assertNotEqual(user.password, user.palabra_secreta_hash)
        self.assertEqual(LogAuditoria.objects.get().accion, "USER_REGISTERED")
        self.assertEqual(LogAuditoria.objects.get().ip_origen, "127.0.0.1")
        self.assertEqual(response.data["data"]["correo_electronico"], user.correo_electronico)
        for secret in ("contrasena", "palabra_secreta", "contrasena_hash", "palabra_secreta_hash"):
            self.assertNotIn(secret, str(response.data))

    def test_contrasena_de_ocho_caracteres_es_valida_y_siete_no(self):
        corta = self.client.post(
            URL, payload() | {"contrasena": "Clave8!"}, format="json"
        )
        self.assertEqual(corta.status_code, 400, corta.data)
        self.assertIn("contrasena", corta.data["error"]["fields"])

        valida = self.client.post(
            URL, payload() | {"contrasena": "Clave8!X"}, format="json"
        )
        self.assertEqual(valida.status_code, 201, valida.data)
        self.assertTrue(Usuario.objects.get().check_password("Clave8!X"))

    def test_correo_existente_responde_conflicto_aun_con_mayusculas(self):
        Usuario.objects.create(
            correo_electronico="ANA.PEREZ@EJEMPLO.COM",
            password=make_password("UnaFraseSeguraPara2026"),
            nombre_completo="Ana Original",
            palabra_secreta_hash="hash-de-prueba",
        )
        response = self.client.post(URL, payload(), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "CORREO_EN_USO")
        self.assertEqual(Usuario.objects.count(), 1)

    def test_rechaza_campos_extras_y_tipos_incorrectos(self):
        for change in ({"nivel_rol": 0}, {"nombre_completo": 123}, {"contrasena": None}):
            with self.subTest(change=change):
                data = payload()
                data.update(change)
                response = self.client.post(URL, data, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_rechaza_secretos_compuestos_solo_de_espacios(self):
        data = payload()
        data["palabra_secreta"] = " " * 13
        response = self.client.post(URL, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("palabra_secreta", response.data["error"]["fields"])

    def test_conserva_espacios_de_un_secreto_valido(self):
        data = payload()
        data["palabra_secreta"] = "  frase privada suficientemente larga  "
        response = self.client.post(URL, data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(check_password(data["palabra_secreta"], Usuario.objects.get().palabra_secreta_hash))

    def test_json_invalido_y_tipo_de_contenido(self):
        malformed = self.client.post(URL, data='{"incompleto":', content_type="application/json")
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.data["error"]["code"], "INVALID_JSON")
        wrong_type = self.client.post(URL, data="texto", content_type="text/plain")
        self.assertEqual(wrong_type.status_code, 415)
        self.assertEqual(wrong_type.data["error"]["code"], "UNSUPPORTED_MEDIA_TYPE")

    def test_auditoria_obligatoria_revierte_el_alta(self):
        with patch.object(LogAuditoria.objects, "create", side_effect=IntegrityError("audit failure")):
            with self.assertRaises(IntegrityError):
                registrar_usuario(payload() | {"correo_electronico": "ana.perez@ejemplo.com"})
        self.assertEqual(Usuario.objects.count(), 0)

    @override_settings(REGISTRATION_IP_RATE="2/hour", REGISTRATION_EMAIL_RATE="10/hour")
    def test_limite_por_ip(self):
        for i in range(2):
            response = self.client.post(URL, payload(f"ana{i}@ejemplo.com"), format="json")
            self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post(URL, payload("ana2@ejemplo.com"), format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"]["code"], "RATE_LIMITED")
        self.assertIn("Retry-After", response)

    @override_settings(REGISTRATION_IP_RATE="20/hour", REGISTRATION_EMAIL_RATE="2/hour")
    def test_limite_por_correo_normalizado(self):
        for correo in ("ANA@EJEMPLO.COM", "ana@ejemplo.com"):
            response = self.client.post(URL, payload(correo), format="json")
            self.assertIn(response.status_code, (201, 409))
        response = self.client.post(URL, payload("Ana@Ejemplo.com"), format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"]["code"], "RATE_LIMITED")

    def test_falla_temporal_de_base_responde_503(self):
        with patch(
            "auth_workspaces.views.registrar_usuario",
            side_effect=OperationalError("base no disponible"),
        ):
            response = self.client.post(URL, payload(), format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"]["code"], "SERVICE_UNAVAILABLE")

    def test_openapi_contiene_registro(self):
        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(URL, response.json()["paths"])
        docs = self.client.get("/api/docs/")
        self.assertEqual(docs.status_code, 200)


class RegistroConcurrenteTests(TransactionTestCase):
    def setUp(self):
        cache.clear()

    def test_solicitudes_concurrentes_no_duplican_correo(self):
        barrier = Barrier(2)

        def register():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                client = APIClient()
                return client.post(URL, payload("carrera@ejemplo.com"), format="json")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: register(), range(2)))

        self.assertEqual(sorted(response.status_code for response in statuses), [201, 409])
        self.assertEqual(
            Usuario.objects.filter(correo_electronico="carrera@ejemplo.com").count(), 1
        )
