from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.exceptions import (
    AuthenticationFailed, NotAuthenticated, NotFound, PermissionDenied, ValidationError,
)

from auth_workspaces.models import Usuario
from auth_workspaces.permisos_administracion import (
    AccionOrganizacion, ExigeSuperusuario, autorizar_organizacion,
)
from auth_workspaces.serializers import PerfilPatchSerializer, RegistroInputSerializer


USUARIO_ID = UUID("a0000000-0000-4000-8000-000000000001")
ORGANIZACION_ID = UUID("b0000000-0000-4000-8000-000000000001")
OTRA_ORGANIZACION_ID = UUID("b0000000-0000-4000-8000-000000000002")


class PermisosAdministracionTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=USUARIO_ID, is_authenticated=True)
        self.cuenta = SimpleNamespace(pk=USUARIO_ID, is_active=True, is_2fa_enabled=False)
        self.usuarios = self.enterContext(patch(
            "auth_workspaces.permisos_administracion.Usuario.objects"
        ))
        self.usuarios.only.return_value.get.return_value = self.cuenta
        self.miembros = self.enterContext(patch(
            "auth_workspaces.permisos_administracion.MiembroOrganizacion.objects"
        ))
        self.rol = self.miembros.filter.return_value.values_list.return_value.first
        self.rol.return_value = 0

    def autorizar(self, accion=AccionOrganizacion.LISTAR_MIEMBROS, org=ORGANIZACION_ID):
        return autorizar_organizacion(self.actor, org, accion)

    def test_matriz_roles_por_accion_sin_orden_numerico(self):
        for accion in AccionOrganizacion:
            for nivel in (0, 1, 2, 3):
                with self.subTest(accion=accion, nivel=nivel):
                    self.rol.return_value = nivel
                    if nivel == 0 or accion == AccionOrganizacion.LISTAR_MIEMBROS:
                        ambito = self.autorizar(accion)
                        self.assertEqual(ambito.organizacion_id, ORGANIZACION_ID)
                        self.assertEqual(ambito.nivel_rol, nivel)
                    else:
                        with self.assertRaises(PermissionDenied):
                            self.autorizar(accion)

    def test_consulta_cuenta_y_membresia_exactas_sin_escrituras(self):
        self.autorizar()
        self.usuarios.only.assert_called_once_with("id", "is_active", "is_2fa_enabled")
        self.usuarios.only.return_value.get.assert_called_once_with(pk=USUARIO_ID)
        self.miembros.filter.assert_called_once_with(
            usuario_id=USUARIO_ID, organizacion_id=ORGANIZACION_ID
        )
        self.miembros.filter.return_value.values_list.assert_called_once_with("nivel_rol", flat=True)
        self.assertEqual([c[0] for c in self.usuarios.mock_calls], ["only", "only().get"])
        self.assertEqual([c[0] for c in self.miembros.mock_calls], [
            "filter", "filter().values_list", "filter().values_list().first",
        ])

    def test_anonimo_no_consulta_repositorios(self):
        for actor in (None, AnonymousUser()):
            with self.subTest(actor=actor), self.assertRaises(NotAuthenticated):
                autorizar_organizacion(actor, ORGANIZACION_ID, AccionOrganizacion.LISTAR_MIEMBROS)
        self.usuarios.only.assert_not_called()
        self.miembros.filter.assert_not_called()

    def test_cuenta_inactiva_2fa_o_eliminada_no_consulta_membresia(self):
        for activo, segundo_factor in ((False, False), (True, True)):
            self.cuenta.is_active = activo
            self.cuenta.is_2fa_enabled = segundo_factor
            with self.subTest(activo=activo), self.assertRaises(AuthenticationFailed):
                self.autorizar()
        self.usuarios.only.return_value.get.side_effect = Usuario.DoesNotExist()
        with self.assertRaises(AuthenticationFailed):
            self.autorizar()
        self.miembros.filter.assert_not_called()

    def test_ambito_explicito_invalido_no_activa_creacion_legada(self):
        for org in (None, "", "no-es-uuid", 123):
            with self.subTest(org=org), self.assertRaises(ValidationError):
                self.autorizar(org=org)
        self.miembros.filter.assert_not_called()

    def test_org_ajena_oculta_existencia_y_no_reutiliza_ambito(self):
        self.autorizar()
        self.rol.return_value = None
        with self.assertRaises(NotFound):
            self.autorizar(org=OTRA_ORGANIZACION_ID)
        self.miembros.filter.assert_called_with(
            usuario_id=USUARIO_ID, organizacion_id=OTRA_ORGANIZACION_ID
        )

    def test_rol_revocado_se_reconsulta_en_siguiente_peticion(self):
        self.autorizar(AccionOrganizacion.CAMBIAR_ROL)
        self.rol.return_value = 3
        with self.assertRaises(PermissionDenied):
            self.autorizar(AccionOrganizacion.CAMBIAR_ROL)
        self.rol.return_value = None
        with self.assertRaises(NotFound):
            self.autorizar()
        self.assertEqual(self.miembros.filter.call_count, 3)

    def test_cuenta_deshabilitada_se_reconsulta(self):
        self.autorizar()
        self.cuenta.is_active = False
        with self.assertRaises(AuthenticationFailed):
            self.autorizar()
        self.assertEqual(self.usuarios.only.return_value.get.call_count, 2)
        self.assertEqual(self.miembros.filter.call_count, 1)

    def test_accion_o_rol_desconocidos_denegados(self):
        for accion in (None, "listar_miembros", "purgar", 0):
            with self.subTest(accion=accion), self.assertRaises(PermissionDenied):
                self.autorizar(accion)
        self.miembros.filter.assert_not_called()
        for nivel in (-1, 4, "0", True):
            self.rol.return_value = nivel
            with self.subTest(nivel=nivel), self.assertRaises(PermissionDenied):
                self.autorizar()

    def test_fallo_repositorio_no_usa_autorizacion_previa(self):
        self.autorizar()
        self.rol.side_effect = OperationalError("fallo sintético")
        with self.assertRaises(OperationalError):
            self.autorizar()
        self.usuarios.only.return_value.get.side_effect = OperationalError("fallo sintético")
        with self.assertRaises(OperationalError):
            self.autorizar()

    def test_global_denegado_incluso_con_atributos_y_claims_privilegiados(self):
        for nivel in (0, 1, 2, 3):
            self.actor.nivel_rol = nivel
            self.actor.is_superuser = True
            self.actor.es_superusuario = True
            self.cuenta.is_superuser = True
            request = SimpleNamespace(user=self.actor, auth={"is_superuser": True})
            with self.subTest(nivel=nivel):
                self.assertIs(ExigeSuperusuario().has_permission(request, None), False)
        self.miembros.filter.assert_not_called()

    def test_global_rechaza_anonimo_inactivo_y_fallo_repositorio(self):
        permiso = ExigeSuperusuario()
        with self.assertRaises(NotAuthenticated):
            permiso.has_permission(SimpleNamespace(user=None), None)
        self.cuenta.is_active = False
        with self.assertRaises(AuthenticationFailed):
            permiso.has_permission(SimpleNamespace(user=self.actor), None)
        self.usuarios.only.return_value.get.side_effect = OperationalError("fallo sintético")
        with self.assertRaises(OperationalError):
            permiso.has_permission(SimpleNamespace(user=self.actor), None)


class EntradasPrivilegiadasTests(SimpleTestCase):
    def test_registro_y_perfil_rechazan_escalada_antes_de_persistir(self):
        registro = {
            "nombre_completo": "Cuenta sintética",
            "correo_electronico": "offline@example.test",
            "contrasena": "clave-sintetica-larga",
            "palabra_secreta": "frase-sintetica-distinta",
        }
        for clase, datos in (
            (RegistroInputSerializer, registro),
            (PerfilPatchSerializer, {"nombre_completo": "Cuenta sintética"}),
        ):
            for campo, valor in (
                ("is_superuser", True), ("es_superusuario", True),
                ("nivel_rol", 0), ("rol", "PROPIETARIO"),
            ):
                with self.subTest(serializer=clase.__name__, campo=campo):
                    serializer = clase(data={**datos, campo: valor})
                    self.assertFalse(serializer.is_valid())
                    self.assertIn(campo, serializer.errors)

    def test_campos_actuales_conservan_validacion(self):
        serializer = PerfilPatchSerializer(data={
            "nombre_completo": " Cuenta ", "correo_electronico": "OFFLINE@example.test",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {
            "nombre_completo": "Cuenta", "correo_electronico": "offline@example.test",
        })
