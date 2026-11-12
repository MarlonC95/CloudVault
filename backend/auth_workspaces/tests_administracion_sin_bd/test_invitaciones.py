from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from auth_workspaces import invitaciones as servicio
from auth_workspaces.models import InvitacionOrganizacion as Invitacion, Usuario

PROPIETARIO, DESTINO, AJENO, ORG, ID = (uuid4() for _ in range(5))
CORREO = "miembro@example.test"


def cuenta(id, correo=CORREO):
    return Usuario(id=id, correo_electronico=correo, is_active=True, is_2fa_enabled=False)


class InvitacionesServicioTests(SimpleTestCase):
    def setUp(self):
        self.ahora = timezone.now()
        self.invitacion = Invitacion(
            id=ID, organizacion_id=ORG, destinatario_usuario_id=DESTINO, invitado_por_id=PROPIETARIO,
            nivel_rol=2, fecha_creacion=self.ahora, fecha_expiracion=self.ahora + timedelta(hours=48),
        )
        self.enterContext(patch.object(self.invitacion, "save"))
        self.manager = self.enterContext(patch.object(Invitacion, "objects"))
        self.query = self.manager.filter.return_value
        self.query.values_list.return_value.first.return_value = ORG
        self.query.select_for_update.return_value.filter.return_value.first.return_value = self.invitacion
        self.manager.create.return_value = self.invitacion
        self.bloqueada = self.manager.select_for_update.return_value.filter.return_value
        self.bloqueada.first.return_value = None
        self.miembros = self.enterContext(patch("auth_workspaces.invitaciones.MiembroOrganizacion.objects"))
        self.miembros.filter.return_value.exists.return_value = True
        self.repo = self.enterContext(patch("auth_workspaces.invitaciones.RepositorioMiembros")).return_value
        self.repo.transaccion.return_value = nullcontext()
        self.repo.objetivo.return_value = None
        self.usuarios = self.enterContext(patch("auth_workspaces.invitaciones.Usuario.objects"))
        self.usuarios.filter.return_value.values_list.return_value = [DESTINO]
        self.cuentas = self.enterContext(patch("auth_workspaces.invitaciones._cuentas_bloqueadas",
            return_value={PROPIETARIO: cuenta(PROPIETARIO), DESTINO: cuenta(DESTINO)}))
        self.tipo = self.enterContext(patch("auth_workspaces.invitaciones.exigir_compartida"))
        self.plan = self.enterContext(patch("auth_workspaces.invitaciones._exigir_plan"))
        self.eventos = self.enterContext(patch("auth_workspaces.invitaciones.LogAuditoria.objects"))
        self.enterContext(patch("auth_workspaces.invitaciones.timezone.now", return_value=self.ahora))

    def enviar(self, rol="OPERATIVO_NV2"):
        return servicio.enviar_invitacion(PROPIETARIO, ORG, CORREO, rol)

    def decidir(self, decision, actor=DESTINO):
        return servicio.decidir_invitacion(actor, ID, decision)

    def test_enviar_guarda_destinatario_rol_y_caducidad_sin_membresia(self):
        self.assertEqual(self.enviar(), (self.invitacion, True))
        self.repo.autorizar.assert_called_once_with(PROPIETARIO, ORG)
        self.cuentas.assert_called_once_with(PROPIETARIO, DESTINO)
        self.manager.create.assert_called_once_with(
            organizacion_id=ORG, invitado_por_id=PROPIETARIO, destinatario_usuario_id=DESTINO,
            nivel_rol=2, fecha_creacion=self.ahora, fecha_expiracion=self.ahora + timedelta(hours=48),
        )
        self.miembros.create.assert_not_called()
        self.assertEqual(self.eventos.create.call_args.kwargs["accion"], "INVITATION_CREATED")

    def test_sin_membresia_o_sin_rol_owner_no_consulta_el_correo(self):
        for existencia, error in [([False], NotFound), ([True, False], PermissionDenied)]:
            with self.subTest(error=error):
                self.miembros.filter.return_value.exists.side_effect = existencia
                with self.assertRaises(error):
                    self.enviar()
        self.usuarios.filter.assert_not_called()

    def test_correo_ambiguo_o_cuenta_deshabilitada_no_invita(self):
        self.usuarios.filter.return_value.values_list.return_value = [DESTINO, AJENO]
        with self.assertRaises(ValidationError):
            self.enviar()
        self.usuarios.filter.return_value.values_list.return_value = [DESTINO]
        self.cuentas.return_value[DESTINO].is_active = False
        with self.assertRaises(ValidationError):
            self.enviar()
        self.manager.create.assert_not_called()

    def test_no_reenvia_pendiente_ni_cambia_su_rol(self):
        self.bloqueada.first.return_value = self.invitacion
        self.assertEqual(self.enviar(), (self.invitacion, False))
        with self.assertRaises(servicio.ConflictoInvitacion) as error:
            self.enviar("LECTOR_NV1")
        self.assertEqual(error.exception.get_codes(), "INVITATION_PENDING")
        self.manager.create.assert_not_called()
        self.eventos.create.assert_not_called()

    def test_reemision_cierra_pendiente_vencida(self):
        self.bloqueada.first.return_value = self.invitacion
        self.invitacion.fecha_expiracion = self.ahora
        self.assertTrue(self.enviar()[1])
        self.assertEqual(self.invitacion.estado, Invitacion.VENCIDA)
        self.assertEqual(self.invitacion.fecha_resolucion, self.ahora)
        self.assertEqual([e.kwargs["accion"] for e in self.eventos.create.call_args_list],
                         ["INVITATION_EXPIRED", "INVITATION_CREATED"])

    def test_miembro_existente_no_recibe_invitacion(self):
        self.repo.objetivo.return_value = object()
        with self.assertRaises(servicio.ConflictoInvitacion) as error:
            self.enviar()
        self.assertEqual(error.exception.get_codes(), "MEMBER_EXISTS")
        self.manager.create.assert_not_called()

    def test_aceptar_crea_membresia_y_repetir_conserva_resultado(self):
        self.assertEqual(self.decidir(Invitacion.ACEPTADA).estado, Invitacion.ACEPTADA)
        self.assertEqual(self.decidir(Invitacion.ACEPTADA).estado, Invitacion.ACEPTADA)
        self.repo.autorizar.assert_called_once_with(PROPIETARIO, ORG)
        self.tipo.assert_called_once_with(ORG)
        self.plan.assert_called_once_with(ORG)
        self.miembros.create.assert_called_once_with(
            organizacion_id=ORG, usuario_id=DESTINO, nivel_rol=2, fecha_union=self.ahora,
        )
        self.invitacion.save.assert_called_once_with(update_fields=["estado", "fecha_resolucion"])
        self.assertEqual(self.invitacion.fecha_resolucion, self.ahora)
        self.assertEqual(self.eventos.create.call_args.kwargs["accion"], "INVITATION_ACCEPTED")
        self.eventos.create.assert_called_once()

    def test_aceptar_prepara_mi_unidad_para_cuenta_legada_sin_membresias(self):
        self.miembros.filter.return_value.exists.return_value = False
        with patch.object(servicio, "asegurar_espacio_personal") as personal:
            self.decidir(Invitacion.ACEPTADA)
        personal.assert_called_once_with(DESTINO)
        self.miembros.create.assert_called_once()

    def test_rechazar_no_da_membresia_y_no_permite_aceptar_luego(self):
        self.assertEqual(self.decidir(Invitacion.RECHAZADA).estado, Invitacion.RECHAZADA)
        self.assertEqual(self.decidir(Invitacion.RECHAZADA).estado, Invitacion.RECHAZADA)
        with self.assertRaises(servicio.ConflictoInvitacion):
            self.decidir(Invitacion.ACEPTADA)
        self.miembros.create.assert_not_called()
        self.assertEqual(self.eventos.create.call_args.kwargs["accion"], "INVITATION_REJECTED")
        self.eventos.create.assert_called_once()

    def test_destinatario_ajeno_no_encuentra_invitacion(self):
        self.query.values_list.return_value.first.return_value = None
        with self.assertRaises(NotFound):
            self.decidir(Invitacion.ACEPTADA, AJENO)
        self.manager.filter.assert_called_once_with(pk=ID, destinatario_usuario_id=AJENO)
        self.repo.transaccion.assert_not_called()
        self.miembros.create.assert_not_called()

    def test_vencimiento_revocacion_o_espacio_no_compartido_impiden_aceptar(self):
        self.invitacion.fecha_expiracion = self.ahora
        with self.assertRaises(servicio.ConflictoInvitacion):
            self.decidir(Invitacion.ACEPTADA)
        self.invitacion.fecha_expiracion = self.ahora + timedelta(hours=1)
        self.invitacion.estado = Invitacion.REVOCADA
        with self.assertRaises(servicio.ConflictoInvitacion):
            self.decidir(Invitacion.ACEPTADA)
        self.invitacion.estado = Invitacion.PENDIENTE
        self.tipo.side_effect = PermissionDenied()
        with self.assertRaises(PermissionDenied):
            self.decidir(Invitacion.ACEPTADA)
        self.miembros.create.assert_not_called()
        self.eventos.create.assert_not_called()

    def test_revocacion_exige_propietario_y_org_exacta(self):
        self.bloqueada.first.return_value = self.invitacion
        servicio.revocar_invitacion(PROPIETARIO, ORG, ID)
        self.repo.autorizar.assert_called_once_with(PROPIETARIO, ORG)
        self.manager.select_for_update.return_value.filter.assert_called_once_with(pk=ID, organizacion_id=ORG)
        self.assertEqual(self.invitacion.estado, Invitacion.REVOCADA)
        self.miembros.create.assert_not_called()

    def test_creacion_explicita_usa_plan_gratuito_y_clave_estable(self):
        orgs = self.enterContext(patch("auth_workspaces.invitaciones.Organizacion.objects"))
        orgs.filter.return_value.first.side_effect = [None, SimpleNamespace(nombre="Equipo", tipo="COMPARTIDO")]
        planes = self.enterContext(patch("auth_workspaces.invitaciones.Plan.objects"))
        planes.filter.return_value.first.return_value = SimpleNamespace(pk=1)
        inicializar = self.enterContext(patch("auth_workspaces.invitaciones.crear_espacio"))
        self.assertTrue(servicio.crear_organizacion_compartida(PROPIETARIO, ORG, "Equipo"))
        self.assertFalse(servicio.crear_organizacion_compartida(PROPIETARIO, ORG, "Equipo"))
        inicializar.assert_called_once_with(self.cuentas.return_value[PROPIETARIO],
            nombre="Equipo", tipo="COMPARTIDO", organizacion_id=ORG, plan_id=1)
        self.eventos.create.assert_called_once()


class InvitacionesHTTPTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(cuenta(DESTINO))
        self.invitacion = Invitacion(id=ID, organizacion_id=ORG, nivel_rol=1, fecha_expiracion=timezone.now())
        self.invitacion.organizacion = servicio.Organizacion(id=ORG, nombre="Equipo")

    def test_bandeja_no_depende_del_selector_y_usa_identidad_autenticada(self):
        with (
            patch("auth_workspaces.views_invitaciones._cuenta_vigente", return_value=cuenta(DESTINO)),
            patch.object(servicio, "pendientes_recibidas", return_value=[self.invitacion]) as consulta,
        ):
            respuesta = self.client.get("/api/v1/organizaciones/invitaciones/recibidas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertEqual(respuesta.json()["data"]["results"][0]["organizacion_nombre"], "Equipo")
        consulta.assert_called_once_with(DESTINO)

    def test_decision_no_admite_rol_actor_u_org_en_cuerpo(self):
        ruta = f"/api/v1/organizaciones/invitaciones/{ID}/decision/"
        with patch.object(servicio, "decidir_invitacion", return_value=self.invitacion) as decidir:
            self.assertEqual(self.client.post(ruta, {"decision": "ACEPTAR", "actor": str(AJENO)}, format="json").status_code, 400)
            decidir.assert_not_called()
            self.assertEqual(self.client.post(ruta, {"decision": "RECHAZAR"}, format="json").status_code, 200)
            decidir.assert_called_once_with(DESTINO, ID, Invitacion.RECHAZADA)

    def test_enviar_en_ruta_de_invitacion_no_colisiona_con_miembro(self):
        ruta = f"/api/v1/organizaciones/{ORG}/miembros/invitar/"
        with patch.object(servicio, "enviar_invitacion", return_value=(self.invitacion, True)) as enviar:
            respuesta = self.client.post(ruta, {"rol": "LECTOR_NV1", "correo_electronico": CORREO.upper()}, format="json")
        self.assertEqual(respuesta.status_code, 201)
        enviar.assert_called_once_with(DESTINO, ORG, CORREO, "LECTOR_NV1")
