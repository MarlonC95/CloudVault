"""Password recovery tests against isolated PostgreSQL."""

from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient, APIRequestFactory

from auth_workspaces.authentication import CloudVaultJWTAuthentication
from auth_workspaces.models import LogAuditoria, Usuario
from auth_workspaces.recovery import recuperar_contrasena


URL = "/api/v1/auth/recuperar-contrasena/"
LOGIN_URL = "/api/v1/auth/login/"
OLD_PASSWORD = "UnaFraseSeguraPara2026"
NEW_PASSWORD = "OtraFraseSeguraPara2027"
SECRET = "Recuerdo privado de hace años"


def payload(correo="ana.perez@ejemplo.com"):
    return {
        "correo": correo,
        "palabra_secreta": SECRET,
        "nueva_contrasena": NEW_PASSWORD,
        "confirmar_contrasena": NEW_PASSWORD,
    }


class RecuperacionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.usuario = Usuario.objects.create(
            correo_electronico="ana.perez@ejemplo.com",
            password=make_password(OLD_PASSWORD),
            nombre_completo="Ana Pérez",
            palabra_secreta_hash=make_password(SECRET),
        )

    def test_recuperacion_valida_cambia_solo_password_audita_e_invalida_access(self):
        old_login = self.client.post(
            LOGIN_URL,
            {"correo": self.usuario.correo_electronico, "contrasena": OLD_PASSWORD},
            format="json",
        )
        self.assertEqual(old_login.status_code, 200, old_login.data)
        old_access = old_login.data["data"]["tokens"]["access"]
        old_secret_hash = self.usuario.palabra_secreta_hash

        response = self.client.post(
            URL, payload("  ANA.PEREZ@EJEMPLO.COM  "), format="json", REMOTE_ADDR="127.0.0.1"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"mensaje": "Contraseña restablecida correctamente."})
        self.usuario.refresh_from_db()
        self.assertFalse(check_password(OLD_PASSWORD, self.usuario.password))
        self.assertTrue(check_password(NEW_PASSWORD, self.usuario.password))
        self.assertEqual(self.usuario.palabra_secreta_hash, old_secret_hash)
        log = LogAuditoria.objects.get()
        self.assertEqual(log.accion, "PASSWORD_RECOVERED")
        self.assertEqual(log.usuario_id, self.usuario.id)
        self.assertEqual(log.ip_origen, "127.0.0.1")
        self.assertEqual(log.detalles, {})
        for secret in (SECRET, NEW_PASSWORD, self.usuario.password, old_secret_hash):
            self.assertNotIn(secret, str(response.data) + str(log.detalles))

        old_request = APIRequestFactory().get(
            "/privado/", HTTP_AUTHORIZATION=f"Bearer {old_access}"
        )
        with self.assertRaises(AuthenticationFailed):
            CloudVaultJWTAuthentication().authenticate(old_request)

        old_login = self.client.post(
            LOGIN_URL,
            {"correo": self.usuario.correo_electronico, "contrasena": OLD_PASSWORD},
            format="json",
        )
        new_login = self.client.post(
            LOGIN_URL,
            {"correo": self.usuario.correo_electronico, "contrasena": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 200)

    def test_nueva_contrasena_de_ocho_caracteres_es_valida_y_siete_no(self):
        corta = self.client.post(
            URL,
            payload() | {"nueva_contrasena": "Nueva8!", "confirmar_contrasena": "Nueva8!"},
            format="json",
        )
        self.assertEqual(corta.status_code, 400, corta.data)
        self.assertIn("nueva_contrasena", corta.data["error"]["fields"])

        valida = self.client.post(
            URL,
            payload() | {"nueva_contrasena": "Nueva8!X", "confirmar_contrasena": "Nueva8!X"},
            format="json",
        )
        self.assertEqual(valida.status_code, 200, valida.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Nueva8!X"))

    def test_correo_inexistente_y_palabra_incorrecta_comparten_401(self):
        wrong = self.client.post(
            URL, payload() | {"palabra_secreta": "Otra frase equivocada"}, format="json"
        )
        unknown = self.client.post(URL, payload("nadie@ejemplo.com"), format="json")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.data, unknown.data)
        self.assertEqual(
            wrong.data,
            {"error": {"code": "RECOVERY_VERIFICATION_FAILED", "message": "No fue posible verificar los datos proporcionados"}},
        )
        self.usuario.refresh_from_db()
        self.assertTrue(check_password(OLD_PASSWORD, self.usuario.password))
        self.assertEqual(LogAuditoria.objects.count(), 0)

    @override_settings(RECOVERY_IP_RATE="100/hour", RECOVERY_EMAIL_RATE="100/hour")
    def test_contrasenas_distintas_debiles_campos_vacios_y_extras(self):
        invalid = (
            payload() | {"confirmar_contrasena": "Diferente2027Larga"},
            payload() | {"nueva_contrasena": "corta", "confirmar_contrasena": "corta"},
            payload() | {"nueva_contrasena": " " * 12, "confirmar_contrasena": " " * 12},
            payload() | {"nueva_contrasena": SECRET, "confirmar_contrasena": SECRET},
            {"correo": "", "palabra_secreta": "", "nueva_contrasena": "", "confirmar_contrasena": ""},
            {"correo": self.usuario.correo_electronico},
            payload() | {"nivel_rol": 0},
            payload() | {"palabra_secreta": 123},
        )
        for body in invalid:
            with self.subTest(body=body):
                response = self.client.post(URL, body, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.usuario.refresh_from_db()
        self.assertTrue(check_password(OLD_PASSWORD, self.usuario.password))
        self.assertEqual(LogAuditoria.objects.count(), 0)

    @override_settings(RECOVERY_IP_RATE="20/hour", RECOVERY_EMAIL_RATE="2/hour")
    def test_limite_de_intentos_por_correo(self):
        wrong = payload() | {"palabra_secreta": "Otra frase equivocada"}
        for correo in ("ANA.PEREZ@EJEMPLO.COM", "ana.perez@ejemplo.com"):
            response = self.client.post(URL, wrong | {"correo": correo}, format="json")
            self.assertEqual(response.status_code, 401)
        response = self.client.post(URL, wrong, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"]["code"], "RATE_LIMITED")
        self.assertIn("Retry-After", response)

    def test_fallo_de_auditoria_revierte_contrasena(self):
        with patch.object(LogAuditoria.objects, "create", side_effect=IntegrityError("audit failure")):
            with self.assertRaises(IntegrityError):
                recuperar_contrasena(payload())
        self.usuario.refresh_from_db()
        self.assertTrue(check_password(OLD_PASSWORD, self.usuario.password))
        self.assertEqual(LogAuditoria.objects.count(), 0)

    def test_openapi_contiene_recuperacion(self):
        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(URL, response.json()["paths"])
