from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from auth_workspaces.models import Usuario


CORTE = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
ORG = UUID("b0000000-0000-4000-8000-000000000001")
OTRA_ORG = UUID("b0000000-0000-4000-8000-000000000002")
USUARIO = UUID("a0000000-0000-4000-8000-000000000001")
RECURSO = UUID("c0000000-0000-4000-8000-000000000001")


class AuditoriaOrganizacionHTTPTests(SimpleTestCase):
    def setUp(self):
        self.cuenta = Usuario(id=USUARIO, password="synthetic-offline-hash", is_active=True)
        self.usuarios = self.enterContext(patch("auth_workspaces.models.Usuario.objects"))
        self.usuarios.get.return_value = self.cuenta
        self.usuarios.only.return_value.get.return_value = self.cuenta
        self.miembros = self.enterContext(patch(
            "auth_workspaces.permisos_administracion.MiembroOrganizacion.objects"
        ))
        self.rol = self.miembros.filter.return_value.values_list.return_value.first
        self.rol.return_value = 0
        self.logs = self.enterContext(patch("auth_workspaces.auditoria_organizaciones.LogAuditoria.objects"))
        self.repo = self.logs.using.return_value
        self.consulta = self.repo.filter.return_value
        self.consulta.filter.return_value = self.consulta
        self.ordenada = self.consulta.order_by.return_value
        self.ordenada.count.return_value = 1
        self.fila = {
            "id": 17, "organizacion_id": ORG, "usuario_id": USUARIO,
            "accion": "PAPELERA_PURGADO", "fecha_evento": CORTE - timedelta(days=1),
            "detalles": {"recurso_id": str(RECURSO), "bytes_fisicos_purgados": 80,
                         "clave_s3": "synthetic-private-value"},
        }
        self.ordenada.__getitem__.return_value.values.return_value = [self.fila]
        self.atomic = self.enterContext(patch("auth_workspaces.auditoria_organizaciones.transaction.atomic"))
        self.atomic.return_value.__exit__.return_value = False
        self.reloj = self.enterContext(patch("auth_workspaces.views_auditoria.timezone.now", return_value=CORTE))
        self.client = APIClient()
        self.token = AccessToken.for_user(self.cuenta)
        self.token["is_superuser"] = True
        self.token["nivel_rol"] = 0
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.url = f"/api/v1/organizaciones/{ORG}/auditoria/"

    def test_owner_lee_salida_exacta_y_registra_un_evento_minimo(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "count": 1, "page_size": 50, "next": None, "previous": None,
            "results": [{
                "id": 17, "organizacion_id": str(ORG), "usuario_id": str(USUARIO),
                "accion": "PAPELERA_PURGADO", "fecha_evento": "2026-10-30T12:00:00Z",
                "detalles": {"recurso_id": str(RECURSO), "bytes_fisicos_purgados": 80},
            }],
        })
        self.assertNotIn("synthetic-private-value", response.content.decode())
        self.repo.create.assert_called_once_with(
            usuario_id=USUARIO, organizacion_id=ORG, accion="ADMIN_DATA_ACCESSED",
            fecha_evento=CORTE, detalles={
                "version": 1, "operacion": "AUDITORIA_ORGANIZACION",
                "desde": "2026-10-01T12:00:00Z", "hasta": "2026-10-31T12:00:00Z",
                "fecha_corte": "2026-10-31T12:00:00Z", "pagina": 1,
                "page_size": 50, "filtro_accion": False,
            },
        )
        self.reloj.assert_called_once_with()

    def test_lectura_y_evento_usan_mismo_alias_y_frontera(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.atomic.assert_called_once_with(using="default")
        self.logs.using.assert_called_once_with("default")
        self.atomic.return_value.__enter__.assert_called_once_with()
        self.atomic.return_value.__exit__.assert_called_once_with(None, None, None)
        self.repo.filter.assert_called_once_with(
            organizacion_id=ORG, fecha_evento__gte=CORTE - timedelta(days=30), fecha_evento__lt=CORTE,
        )
        self.consulta.order_by.assert_called_once_with("-fecha_evento", "-id")
        self.ordenada.__getitem__.assert_called_once_with(slice(0, 50))

    def test_roles_1_a_3_no_leen_ni_generan_eventos_aunque_claim_sea_su(self):
        for rol in (1, 2, 3):
            self.rol.return_value = rol
            with self.subTest(rol=rol):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": {"code": "FORBIDDEN"}})
        self.logs.using.assert_not_called()

    def test_ajena_es_404_antes_de_consultar_auditoria(self):
        self.rol.return_value = None
        response = self.client.get(f"/api/v1/organizaciones/{OTRA_ORG}/auditoria/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")
        self.miembros.filter.assert_called_once_with(usuario_id=USUARIO, organizacion_id=OTRA_ORG)
        self.logs.using.assert_not_called()

    def test_identidad_invalida_no_entra_en_transaccion(self):
        for token, codigo in ((None, "NO_AUTENTICADO"), ("invalid-offline-value", "TOKEN_INVALID")):
            self.client.credentials(**({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}))
            with self.subTest(codigo=codigo):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["error"]["code"], codigo)
        self.atomic.assert_not_called()
        self.logs.using.assert_not_called()

    def test_mismo_jwt_observa_rebaja_retirada_y_estado_inactivo(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.rol.return_value = 3
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.rol.return_value = None
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.cuenta.is_active = False
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.repo.create.assert_called_once()

    def test_filtros_se_acumulan_y_no_se_copia_texto_libre_al_evento(self):
        response = self.client.get(self.url, {
            "usuario_id": str(USUARIO), "accion": " PAPELERA_PURGADO ",
            "desde": "2026-10-20T14:00:00+02:00", "hasta": "2026-10-31T12:00:00Z",
        })
        self.assertEqual(response.status_code, 200)
        self.consulta.filter.assert_any_call(usuario_id=USUARIO)
        self.consulta.filter.assert_any_call(accion="PAPELERA_PURGADO")
        self.assertEqual(self.repo.filter.call_args.kwargs["fecha_evento__gte"], datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
        detalles = self.repo.create.call_args.kwargs["detalles"]
        self.assertIs(detalles["filtro_accion"], True)
        self.assertEqual(detalles["usuario_filtro_id"], str(USUARIO))
        self.assertNotIn("PAPELERA_PURGADO", str(detalles))

    def test_invalido_repetido_o_override_no_consulta_logs(self):
        for query in (
            f"organizacion_id={OTRA_ORG}", "accion=A&accion=B", "page=1&page=1",
            "page_size=101", "usuario_id=bad", "accion=", "desde=2026-01-01",
            "hasta=bad", "desde=2026-10-31T12%3A00%3A00Z", "buscar=x",
        ):
            with self.subTest(query=query):
                response = self.client.get(self.url + "?" + query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.logs.using.assert_not_called()
        self.atomic.assert_not_called()

    def test_cuerpo_get_no_vacio_se_rechaza(self):
        for cuerpo in ("{}", "null", "[]", "synthetic"):
            with self.subTest(cuerpo=cuerpo):
                response = self.client.generic("GET", self.url, data=cuerpo, content_type="application/json")
                self.assertEqual(response.status_code, 400)
        self.atomic.assert_not_called()

    def test_organizacion_invalida_es_error_controlado(self):
        response = self.client.get("/api/v1/organizaciones/no-es-uuid/auditoria/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("organizacion_id", response.json()["error"]["fields"])
        self.logs.using.assert_not_called()

    def test_ventana_366_permitida_y_367_rechazada(self):
        self.assertEqual(self.client.get(self.url, {"desde": (CORTE - timedelta(days=366)).isoformat()}).status_code, 200)
        self.assertEqual(self.client.get(self.url, {"desde": (CORTE - timedelta(days=367)).isoformat()}).status_code, 400)
        self.repo.create.assert_called_once()

    def test_futuro_se_limita_por_corte_y_evento_propio_queda_excluido(self):
        response = self.client.get(self.url, {"hasta": (CORTE + timedelta(days=1)).isoformat()})
        self.assertEqual(response.status_code, 200)
        fin = self.repo.filter.call_args.kwargs["fecha_evento__lt"]
        fecha_evento = self.repo.create.call_args.kwargs["fecha_evento"]
        self.assertEqual(fin, CORTE)
        self.assertFalse(fecha_evento < fin)

    def test_enlace_siguiente_fija_ventana_y_no_pierde_filtros(self):
        self.ordenada.count.return_value = 3
        response = self.client.get(self.url, {"page_size": "1", "usuario_id": str(USUARIO), "accion": "PAPELERA_PURGADO", "hasta": (CORTE + timedelta(days=1)).isoformat()})
        self.assertEqual(response.status_code, 200)
        enlace = urlsplit(response.json()["next"])
        query = parse_qs(enlace.query)
        self.assertEqual(enlace.path, self.url)
        self.assertEqual(query["page"], ["2"])
        self.assertEqual(query["page_size"], ["1"])
        self.assertEqual(query["usuario_id"], [str(USUARIO)])
        self.assertEqual(query["accion"], ["PAPELERA_PURGADO"])
        self.assertEqual(query["hasta"], ["2026-10-31T12:00:00Z"])
        self.reloj.return_value = CORTE + timedelta(hours=1)
        siguiente = self.client.get(enlace.path + "?" + enlace.query)
        self.assertEqual(siguiente.status_code, 200)
        self.assertEqual(self.repo.filter.call_args.kwargs["fecha_evento__lt"], CORTE)

    def test_ultima_pagina_tiene_anterior_y_slice_acotado(self):
        self.ordenada.count.return_value = 3
        response = self.client.get(self.url, {"page": "2", "page_size": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["next"])
        self.assertEqual(parse_qs(urlsplit(response.json()["previous"]).query)["page"], ["1"])
        self.ordenada.__getitem__.assert_called_once_with(slice(2, 4))

    def test_vacia_y_filtro_desconocido_son_lecturas_auditadas(self):
        self.ordenada.count.return_value = 0
        self.ordenada.__getitem__.return_value.values.return_value = []
        response = self.client.get(self.url, {"accion": "ACCION_FUTURA"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.consulta.filter.assert_called_once_with(accion="ACCION_FUTURA")
        self.repo.create.assert_called_once()

    def test_pagina_inexistente_no_se_anuncia_exitosa_ni_crea_evento(self):
        response = self.client.get(self.url, {"page": "2"})
        self.assertEqual(response.status_code, 400)
        self.ordenada.__getitem__.assert_not_called()
        self.repo.create.assert_not_called()

    def test_fuente_inconsistente_no_tiene_exito_parcial(self):
        for cambios in ({"id": "bad"}, {"usuario_id": "bad"}, {"organizacion_id": OTRA_ORG}, {"organizacion_id": None}):
            self.ordenada.__getitem__.return_value.values.return_value = [{**self.fila, **cambios}]
            with self.subTest(campos=list(cambios)):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"error": {"code": "SERVICE_UNAVAILABLE"}})
        self.repo.create.assert_not_called()

    def test_fallo_consulta_no_expone_detalles_ni_registra_exito(self):
        self.ordenada.count.side_effect = OperationalError("synthetic-private-value")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("synthetic-private-value", response.content.decode())
        self.repo.create.assert_not_called()

    def test_fallo_evento_obligatorio_impide_200_y_sale_con_error(self):
        self.repo.create.side_effect = OperationalError("synthetic-private-value")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": {"code": "SERVICE_UNAVAILABLE"}})
        self.assertIs(self.atomic.return_value.__exit__.call_args.args[0], OperationalError)

    def test_dos_filas_no_crean_dos_eventos_ni_se_auditan_recursivamente(self):
        self.ordenada.count.return_value = 2
        self.ordenada.__getitem__.return_value.values.return_value = [self.fila, {**self.fila, "id": 18, "accion": "ADMIN_DATA_ACCESSED", "detalles": {"version": 1, "operacion": "AUDITORIA_ORGANIZACION"}}]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 2)
        self.repo.create.assert_called_once()
        self.ordenada.count.assert_called_once()

    def test_metodos_de_escritura_no_estan_habilitados(self):
        for method in ("POST", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url)
                self.assertEqual(response.status_code, 405)
        self.atomic.assert_not_called()
