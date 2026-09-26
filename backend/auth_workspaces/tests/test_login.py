"""Login contract tests against the isolated PostgreSQL test database."""

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient, APIRequestFactory
from auth_workspaces.authentication import CloudVaultJWTAuthentication

from auth_workspaces.models import Usuario


URL = "/api/v1/auth/login/"
PASSWORD = "UnaFraseSeguraPara2026"


class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.usuario = Usuario.objects.create(
            correo_electronico="ana.perez@ejemplo.com",
            password=make_password(PASSWORD),
            nombre_completo="Ana Pérez",
            palabra_secreta_hash=make_password("Recuerdo privado de hace años"),
        )

    def test_credenciales_correctas_devuelven_200_usuario_y_jwt(self):
        response = self.client.post(
            URL,
            {"correo": "  ANA.PEREZ@EJEMPLO.COM  ", "contrasena": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["usuario"]["correo_electronico"], self.usuario.correo_electronico)
        self.assertEqual(data["usuario"]["id"], str(self.usuario.id))
        for secret in ("contrasena_hash", "palabra_secreta_hash", PASSWORD):
            self.assertNotIn(secret, str(data["usuario"]))
        self.assertTrue(data["tokens"]["refresh"])
        request = APIRequestFactory().get(
            "/privado/", HTTP_AUTHORIZATION=f"Bearer {data['tokens']['access']}"
        )
        authenticated_user, token = CloudVaultJWTAuthentication().authenticate(request)
        self.assertEqual(authenticated_user.id, self.usuario.id)
        self.assertEqual(token["token_type"], "access")

        Usuario.objects.filter(pk=self.usuario.pk).update(is_2fa_enabled=True)
        with self.assertRaises(AuthenticationFailed):
            CloudVaultJWTAuthentication().authenticate(request)

    def test_contrasena_incorrecta_y_correo_inexistente_comparten_401(self):
        incorrecta = self.client.post(
            URL,
            {"correo": self.usuario.correo_electronico, "contrasena": "OtraClaveIncorrecta"},
            format="json",
        )
        inexistente = self.client.post(
            URL,
            {"correo": "nadie@ejemplo.com", "contrasena": PASSWORD},
            format="json",
        )
        self.assertEqual(incorrecta.status_code, 401)
        self.assertEqual(inexistente.status_code, 401)
        self.assertEqual(incorrecta.data, inexistente.data)
        self.assertEqual(
            incorrecta.data,
            {"error": {"code": "INVALID_CREDENTIALS", "message": "Correo o contraseña incorrectos"}},
        )

    def test_campos_vacios_faltantes_o_extras_devuelven_400(self):
        for body in (
            {"correo": "", "contrasena": ""},
            {"correo": self.usuario.correo_electronico},
            {"correo": self.usuario.correo_electronico, "contrasena": PASSWORD, "palabra_secreta": "x"},
        ):
            with self.subTest(body=body):
                response = self.client.post(URL, body, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_cuenta_inactiva_o_con_2fa_no_recibe_tokens(self):
        for changes in ({"is_active": False}, {"is_2fa_enabled": True}):
            Usuario.objects.filter(pk=self.usuario.pk).update(**changes)
            response = self.client.post(
                URL,
                {"correo": self.usuario.correo_electronico, "contrasena": PASSWORD},
                format="json",
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")
            Usuario.objects.filter(pk=self.usuario.pk).update(
                is_active=True, is_2fa_enabled=False
            )

    def test_openapi_publica_login(self):
        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(URL, response.json()["paths"])
