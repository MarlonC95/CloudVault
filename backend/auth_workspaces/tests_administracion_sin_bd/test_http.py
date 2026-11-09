from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

from django.test import SimpleTestCase
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from auth_workspaces.authentication import CloudVaultJWTAuthentication
from auth_workspaces.models import Usuario
from auth_workspaces.permisos_administracion import (
    AccionOrganizacion, ExigeSuperusuario, autorizar_organizacion,
)


class VistaGlobalSoloDePrueba(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [ExigeSuperusuario]
    throttle_classes = []

    def get(self, request):
        raise AssertionError("No consultar datos globales sin fuente privilegiada")


class GuardiaGlobalHTTPTests(SimpleTestCase):
    def setUp(self):
        self.cuenta = Usuario(
            id=UUID("a0000000-0000-4000-8000-000000000001"),
            password="synthetic-hash-for-offline-test-only",
            is_active=True,
        )
        self.usuarios = self.enterContext(patch("auth_workspaces.models.Usuario.objects"))
        self.usuarios.get.return_value = self.cuenta
        self.usuarios.only.return_value.get.return_value = self.cuenta

    def pedir(self, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
        request = APIRequestFactory().get("/ruta-sintetica-no-montada/", **headers)
        return VistaGlobalSoloDePrueba.as_view()(request)

    def test_jwt_valido_con_claim_su_no_alcanza_datos_globales(self):
        token = AccessToken.for_user(self.cuenta)
        token["is_superuser"] = True
        self.cuenta.is_superuser = True
        response = self.pedir(str(token))
        self.assertEqual(response.status_code, 403)
        self.assertEqual([c[0] for c in self.usuarios.mock_calls], [
            "get", "only", "only().get",
        ])

    def test_sin_jwt_o_jwt_invalido_no_consulta_cuenta(self):
        for token in (None, "invalid-offline-value"):
            with self.subTest(presente=token is not None):
                self.assertEqual(self.pedir(token).status_code, 401)
        self.usuarios.get.assert_not_called()
        self.usuarios.only.assert_not_called()

    def test_jwt_expirado_no_consulta_cuenta(self):
        token = AccessToken.for_user(self.cuenta)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(self.pedir(str(token)).status_code, 401)
        self.usuarios.get.assert_not_called()

    def test_jwt_de_cuenta_ahora_inactiva_es_rechazado(self):
        token = AccessToken.for_user(self.cuenta)
        self.cuenta.is_active = False
        self.assertEqual(self.pedir(str(token)).status_code, 401)
        self.usuarios.only.assert_not_called()


class VistaOrganizacionSoloDePrueba(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = []

    def get(self, request, organizacion_id, accion):
        ambito = autorizar_organizacion(request.user, organizacion_id, accion)
        return Response({"organizacion_id": str(ambito.organizacion_id)})


class GuardiaOrganizacionHTTPTests(SimpleTestCase):
    def setUp(self):
        self.organizacion_id = UUID("b0000000-0000-4000-8000-000000000001")
        self.cuenta = Usuario(
            id=UUID("a0000000-0000-4000-8000-000000000001"),
            password="synthetic-hash-for-offline-test-only",
            is_active=True,
        )
        self.usuarios = self.enterContext(patch("auth_workspaces.models.Usuario.objects"))
        self.usuarios.get.return_value = self.cuenta
        self.usuarios.only.return_value.get.return_value = self.cuenta
        self.miembros = self.enterContext(patch(
            "auth_workspaces.permisos_administracion.MiembroOrganizacion.objects"
        ))
        self.rol = self.miembros.filter.return_value.values_list.return_value.first
        self.rol.return_value = 0
        token = AccessToken.for_user(self.cuenta)
        token["nivel_rol"] = 0
        token["is_superuser"] = True
        self.token = str(token)

    def pedir(self, accion=AccionOrganizacion.LISTAR_MIEMBROS, organizacion_id=None):
        request = APIRequestFactory().get(
            "/organizacion-sintetica-no-montada/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        return VistaOrganizacionSoloDePrueba.as_view()(
            request,
            organizacion_id=self.organizacion_id if organizacion_id is None else organizacion_id,
            accion=accion,
        )

    def test_jwt_y_listado_autorizan_solo_la_organizacion_explicita(self):
        for nivel in (0, 1, 2, 3):
            self.rol.return_value = nivel
            with self.subTest(nivel=nivel):
                response = self.pedir()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, {"organizacion_id": str(self.organizacion_id)})
        self.miembros.filter.assert_called_with(
            usuario_id=self.cuenta.pk, organizacion_id=self.organizacion_id,
        )

    def test_claim_de_propietario_no_amplia_el_rol_vigente(self):
        for accion in AccionOrganizacion:
            if accion == AccionOrganizacion.LISTAR_MIEMBROS:
                continue
            for nivel in (0, 1, 2, 3):
                self.rol.return_value = nivel
                with self.subTest(accion=accion, nivel=nivel):
                    self.assertEqual(self.pedir(accion).status_code, 200 if nivel == 0 else 403)

    def test_organizacion_ajena_no_se_autoriza_por_claim(self):
        otra = UUID("b0000000-0000-4000-8000-000000000002")
        self.rol.return_value = None
        self.assertEqual(self.pedir(organizacion_id=otra).status_code, 404)
        self.miembros.filter.assert_called_once_with(
            usuario_id=self.cuenta.pk, organizacion_id=otra,
        )

    def test_mismo_jwt_observa_rebaja_de_rol_y_deshabilitacion(self):
        accion = AccionOrganizacion.CAMBIAR_ROL
        self.assertEqual(self.pedir(accion).status_code, 200)
        self.rol.return_value = 3
        self.assertEqual(self.pedir(accion).status_code, 403)
        self.cuenta.is_active = False
        self.assertEqual(self.pedir(accion).status_code, 401)
        self.assertEqual(self.miembros.filter.call_count, 2)
