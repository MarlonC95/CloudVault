"""Pruebas de §1.4, §1.5 y §2.1-§2.3."""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from auth_workspaces.models import Usuario
from common.testing import (
    agregar_miembro, cliente_autenticado, crear_organizacion, crear_suscripcion, crear_usuario,
    espacio_de_trabajo,
)

REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"
PERFIL = "/api/v1/auth/perfil/"
CAMBIAR = "/api/v1/auth/cambiar-contrasena/"


def tokens_para(usuario_id):
    usuario = Usuario(id=usuario_id, correo_electronico="prueba@example.test", password="hash")
    refresh = RefreshToken.for_user(usuario)
    return str(refresh.access_token), str(refresh)


def espacio_con_password(password="ContraseñaDePrueba123"):
    """Crea un usuario con contraseña Django válida y su espacio de trabajo."""
    usuario = Usuario.objects.create_user(
        correo_electronico="contrasena@example.test",
        password=password,
        nombre_completo="Usuario Contraseña",
    )
    organizacion_id = crear_organizacion()
    agregar_miembro(organizacion_id, usuario.id, 0)
    crear_suscripcion(organizacion_id)
    return usuario.id, organizacion_id


def cliente_real(usuario_id):
    """Cliente autenticado usando el hash real del usuario (CHECK_REVOKE_TOKEN)."""
    usuario = Usuario.objects.get(pk=usuario_id)
    token = RefreshToken.for_user(usuario).access_token
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return cliente


class RefreshTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario_id, _ = espacio_de_trabajo()

    def test_refresh_valido_devuelve_nuevo_par(self):
        _, refresh = tokens_para(self.usuario_id)
        response = APIClient().post(REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    def test_refresh_invalido_es_401_token_invalido(self):
        response = APIClient().post(REFRESH, {"refresh": "token-malformado"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "TOKEN_INVALIDO")


class LogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario_id, _ = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def test_logout_autenticado_devuelve_200(self):
        _, refresh = tokens_para(self.usuario_id)
        response = self.client.post(LOGOUT, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["mensaje"], "Sesión cerrada correctamente.")

    def test_logout_requiere_autenticacion(self):
        response = APIClient().post(LOGOUT, {"refresh": "x"}, format="json")
        self.assertEqual(response.status_code, 401)


class PerfilTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def test_get_perfil_devuelve_datos_y_plan(self):
        response = self.client.get(PERFIL)
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["nombre_completo"], "Usuario Prueba")
        self.assertEqual(data["rol"], "admin")
        self.assertEqual(data["plan"]["id"], "gratuito")
        self.assertIn("almacenamiento", data)

    def test_patch_perfil_actualiza_nombre_y_correo(self):
        response = self.client.patch(
            PERFIL,
            {"nombre_completo": "Nuevo Nombre", "correo_electronico": "nuevo@example.test"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["nombre_completo"], "Nuevo Nombre")
        self.assertEqual(data["correo_electronico"], "nuevo@example.test")

    def test_patch_correo_existente_es_409(self):
        otro_id = crear_usuario("existente@example.test")
        espacio_de_trabajo()  # organización para otro usuario no influye
        response = self.client.patch(
            PERFIL, {"correo_electronico": "existente@example.test"}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "CORREO_EN_USO")


class CambiarContrasenaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario_id, _ = espacio_con_password()
        self.client = cliente_real(self.usuario_id)

    def test_cambio_contrasena_correcto(self):
        response = self.client.post(
            CAMBIAR,
            {
                "contrasena_actual": "ContraseñaDePrueba123",
                "nueva_contrasena": "Xy9#kL2$mN0!pQ",
                "confirmar_contrasena": "Xy9#kL2$mN0!pQ",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["data"]["mensaje"], "La contraseña se actualizó correctamente."
        )

    def test_cambio_contrasena_rechaza_actual_incorrecta(self):
        response = self.client.post(
            CAMBIAR,
            {
                "contrasena_actual": "incorrecta",
                "nueva_contrasena": "Xy9#kL2$mN0!pQ",
                "confirmar_contrasena": "Xy9#kL2$mN0!pQ",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("contrasena_actual", response.data["error"]["fields"])
