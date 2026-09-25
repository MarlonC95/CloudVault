"""Security regression checks that do not connect to a database."""

import os
from pathlib import Path
import runpy
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from auth_workspaces.login import CredencialesInvalidas
from auth_workspaces.services import CorreoEnUso


PASSWORD = "Synthetic-Password!7286"
PHRASE = "Synthetic-Recovery!3951"
TOKEN = "synthetic-token-not-a-real-credential"
REGISTRATION = {
    "nombre_completo": "Persona de prueba",
    "correo_electronico": "seguridad@example.invalid",
    "contrasena": PASSWORD,
    "palabra_secreta": PHRASE,
}
LOGIN = {"correo": REGISTRATION["correo_electronico"], "contrasena": PASSWORD}
RECOVERY = {
    "correo": LOGIN["correo"],
    "palabra_secreta": PHRASE,
    "nueva_contrasena": PASSWORD,
    "confirmar_contrasena": PASSWORD,
}
ENDPOINTS = (
    ("registro", "registrar_usuario", REGISTRATION),
    ("login", "iniciar_sesion", LOGIN),
    ("recuperar-contrasena", "recuperar_contrasena", RECOVERY),
)


class SecureSettingsTests(SimpleTestCase):
    def load_settings(self, **environment):
        path = Path(__file__).resolve().parents[2] / "config" / "settings.py"
        # Never read the developer's secrets or change the active Django settings.
        with patch.dict(os.environ, environment, clear=True), patch("environ.Env.read_env"):
            return runpy.run_path(str(path))

    def test_defaults_disable_debug_and_require_https(self):
        config = self.load_settings(DJANGO_SECRET_KEY="synthetic-key-for-settings-only")
        self.assertFalse(config["DEBUG"])
        self.assertTrue(config["SECURE_SSL_REDIRECT"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])

    def test_missing_or_blank_key_fails_in_both_modes(self):
        for debug in ("True", "False"):
            for key in (None, "", "   "):
                with self.subTest(debug=debug, key=key):
                    environment = {"DJANGO_DEBUG": debug}
                    if key is not None:
                        environment["DJANGO_SECRET_KEY"] = key
                    with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY is required"):
                        self.load_settings(**environment)

    def test_local_debug_requires_explicit_configuration(self):
        config = self.load_settings(
            DJANGO_SECRET_KEY="synthetic-key-for-settings-only", DJANGO_DEBUG="True"
        )
        self.assertTrue(config["DEBUG"])
        self.assertFalse(config["SECURE_SSL_REDIRECT"])


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CACHES={"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "error-security-tests",
    }},
)
class ErrorConfidentialityTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def test_unexpected_errors_hide_secrets_in_response_and_log(self):
        for debug in (True, False):
            for route, operation, body in ENDPOINTS:
                with self.subTest(debug=debug, route=route), override_settings(DEBUG=debug):
                    cache.clear()
                    exception = RuntimeError(f"{PASSWORD} {PHRASE} {TOKEN}")
                    with patch(f"auth_workspaces.views.{operation}", side_effect=exception):
                        with self.assertLogs("auth_workspaces.exceptions", level="ERROR") as logs:
                            response = self.client.post(
                                f"/api/v1/auth/{route}/", body, format="json"
                            )
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(response.json(), {
                        "error": {"code": "INTERNAL_ERROR", "message": "Ocurrió un error interno."}
                    })
                    self.assertIn("application/json", response["Content-Type"])
                    for secret in (PASSWORD, PHRASE, TOKEN):
                        self.assertNotIn(secret, response.content.decode())
                        self.assertNotIn(secret, "\n".join(logs.output))
                    self.assertTrue(all(record.exc_info is None for record in logs.records))
                    self.assertTrue(all(record.stack_info is None for record in logs.records))

    def test_database_errors_remain_generic_503(self):
        for route, operation, body in ENDPOINTS:
            with self.subTest(route=route):
                cache.clear()
                with patch(f"auth_workspaces.views.{operation}", side_effect=OperationalError(PASSWORD)):
                    response = self.client.post(f"/api/v1/auth/{route}/", body, format="json")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["error"]["code"], "SERVICE_UNAVAILABLE")
                self.assertNotIn(PASSWORD, response.content.decode())

    def test_expected_validation_and_authentication_errors_keep_contract(self):
        invalid = self.client.post("/api/v1/auth/login/", {}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "VALIDATION_ERROR")
        with patch("auth_workspaces.views.iniciar_sesion", side_effect=CredencialesInvalidas()):
            denied = self.client.post("/api/v1/auth/login/", LOGIN, format="json")
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.json()["error"]["code"], "INVALID_CREDENTIALS")
        with patch("auth_workspaces.views.registrar_usuario", side_effect=CorreoEnUso()):
            duplicate = self.client.post("/api/v1/auth/registro/", REGISTRATION, format="json")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["error"]["code"], "CORREO_EN_USO")
