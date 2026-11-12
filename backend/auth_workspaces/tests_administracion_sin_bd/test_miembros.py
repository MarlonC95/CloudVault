from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from auth_workspaces.models import Usuario


ORG = UUID("b0000000-0000-4000-8000-000000000001")
OTRA_ORG = UUID("b0000000-0000-4000-8000-000000000002")
USUARIO = UUID("a0000000-0000-4000-8000-000000000001")
OTRO_USUARIO = UUID("a0000000-0000-4000-8000-000000000002")
FECHA = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


class ListadoMiembrosTests(SimpleTestCase):
    def setUp(self):
        self.cuenta = Usuario(id=USUARIO, password="synthetic-offline-hash", is_active=True)
        self.usuarios = self.enterContext(patch("auth_workspaces.organizaciones.Usuario.objects"))
        self.usuarios.get.return_value = self.cuenta
        self.usuarios.only.return_value.get.return_value = self.cuenta
        self.miembros = self.enterContext(patch(
            "auth_workspaces.organizaciones.MiembroOrganizacion.objects"
        ))
        self.rol_actual = self.miembros.filter.return_value.values_list.return_value.first
        self.rol_actual.return_value = 0
        self.lista = self.miembros.filter.return_value.order_by.return_value
        self.lista.count.return_value = 1
        self.fila = {"usuario_id": USUARIO, "nivel_rol": 0, "fecha_union": FECHA}
        self.lista.__getitem__.return_value.values.return_value = [self.fila]
        self.usuarios.filter.return_value.values.return_value = [{
            "id": USUARIO,
            "nombre_completo": "Cuenta de prueba",
            "correo_electronico": "offline@example.test",
            "password": "synthetic-private-value",
            "totp_secret": "synthetic-private-value",
        }]
        self.client = APIClient()
        self.token = AccessToken.for_user(self.cuenta)
        self.token["is_superuser"] = True
        self.token["nivel_rol"] = 0
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.url = f"/api/v1/organizaciones/{ORG}/miembros/"

    def test_roles_0_a_3_leen_proyeccion_publica_exacta(self):
        for nivel, rol in enumerate(("PROPIETARIO", "LECTOR_NV1", "OPERATIVO_NV2", "AVANZADO_NV3")):
            self.rol_actual.return_value = nivel
            self.fila["nivel_rol"] = nivel
            with self.subTest(nivel=nivel):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertEqual(response.json(), {
                    "count": 1, "next": None, "previous": None, "page_size": 50,
                    "results": [{
                        "usuario_id": str(USUARIO), "nombre_completo": "Cuenta de prueba",
                        "correo_electronico": "offline@example.test", "rol": rol,
                        "nivel_rol": nivel, "fecha_ingreso": "2026-10-31T12:00:00Z",
                    }],
                })
                self.assertNotIn("synthetic-private-value", response.content.decode())

    def test_filtro_orden_y_carga_por_lote_solo_de_la_pagina(self):
        self.client.get(self.url)
        self.miembros.filter.assert_any_call(usuario_id=USUARIO, organizacion_id=ORG)
        self.miembros.filter.assert_any_call(organizacion_id=ORG)
        self.miembros.filter.return_value.order_by.assert_called_once_with("fecha_union", "usuario_id")
        self.lista.__getitem__.assert_called_once_with(slice(0, 50))
        self.usuarios.filter.assert_called_once_with(pk__in={USUARIO})
        self.usuarios.filter.return_value.values.assert_called_once_with(
            "id", "nombre_completo", "correo_electronico",
        )

    def test_primera_pagina_y_enlace_preservan_organizacion_y_tamano(self):
        self.lista.count.return_value = 3
        self.lista.__getitem__.return_value.values.return_value = [self.fila, {
            "usuario_id": OTRO_USUARIO, "nivel_rol": 1, "fecha_union": FECHA,
        }]
        self.usuarios.filter.return_value.values.return_value += [{
            "id": OTRO_USUARIO, "nombre_completo": "Otro miembro",
            "correo_electronico": "another@example.test",
        }]
        response = self.client.get(self.url + "?page=1&page_size=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertIsNone(data["previous"])
        next_url = urlsplit(data["next"])
        self.assertEqual(next_url.path, self.url)
        self.assertEqual(parse_qs(next_url.query), {"page": ["2"], "page_size": ["2"]})
        self.lista.__getitem__.assert_called_once_with(slice(0, 2))

    def test_ultima_pagina_y_enlace_anterior(self):
        self.lista.count.return_value = 3
        response = self.client.get(self.url + "?page=2&page_size=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["next"])
        self.assertEqual(urlsplit(data["previous"]).path, self.url)
        self.assertEqual(parse_qs(urlsplit(data["previous"]).query), {
            "page": ["1"], "page_size": ["2"],
        })
        self.lista.__getitem__.assert_called_once_with(slice(2, 4))

    def test_cien_es_tamano_permitido(self):
        response = self.client.get(self.url + "?page_size=100")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 100)
        self.lista.__getitem__.assert_called_once_with(slice(0, 100))

    def test_vacia_en_pagina_inicial_no_carga_usuarios(self):
        self.lista.count.return_value = 0
        self.lista.__getitem__.return_value.values.return_value = []
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "count": 0, "next": None, "previous": None, "page_size": 50, "results": [],
        })
        self.usuarios.filter.assert_not_called()

    def test_pagina_inexistente_es_400_sin_leer_filas(self):
        for count in (0, 1):
            self.lista.count.return_value = count
            for page in ("2", "9" * 50):
                with self.subTest(count=count, page=page):
                    response = self.client.get(self.url + "?page=" + page)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
                    self.assertIn("page", response.json()["error"]["fields"])
        self.lista.__getitem__.assert_not_called()
        self.usuarios.filter.assert_not_called()

    def test_parametros_invalidos_repetidos_o_extra_no_consultan_miembros(self):
        for query in (
            "page=0", "page=-1", "page=1.5", "page=true", "page=", "page=%201",
            "page_size=0",
            "page_size=101", "page_size=", "page_size=1.0", "page=1&page=2",
            "page_size=2&page_size=2", "buscar=cuenta", f"organizacion_id={OTRA_ORG}",
        ):
            with self.subTest(query=query):
                response = self.client.get(self.url + "?" + query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.miembros.filter.assert_not_called()
        self.lista.count.assert_not_called()

    def test_get_rechaza_cualquier_cuerpo_no_vacio(self):
        for body in ("{}", "null", "[]", "synthetic"):
            with self.subTest(body=body):
                response = self.client.generic("GET", self.url, data=body, content_type="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.miembros.filter.assert_not_called()

    def test_uuid_mal_formado_no_consulta_listado(self):
        response = self.client.get("/api/v1/organizaciones/no-es-uuid/miembros/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("organizacion_id", response.json()["error"]["fields"])
        self.lista.count.assert_not_called()

    def test_sin_sesion_o_jwt_invalido_no_consulta_datos(self):
        for token, code in ((None, "NO_AUTENTICADO"), ("invalid-offline-value", "TOKEN_INVALID")):
            self.client.credentials(**({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}))
            with self.subTest(code=code):
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"error": {"code": code}})
                self.assertEqual(response["WWW-Authenticate"].split()[0], "Bearer")
        self.usuarios.get.assert_not_called()
        self.miembros.filter.assert_not_called()

    def test_jwt_expirado_no_consulta_datos(self):
        self.token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "TOKEN_INVALID")
        self.miembros.filter.assert_not_called()

    def test_organizacion_ajena_es_404_sin_leer_sus_miembros(self):
        self.rol_actual.return_value = None
        response = self.client.get(f"/api/v1/organizaciones/{OTRA_ORG}/miembros/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": {"code": "NOT_FOUND"}})
        self.miembros.filter.assert_called_once_with(usuario_id=USUARIO, organizacion_id=OTRA_ORG)
        self.lista.count.assert_not_called()

    def test_rol_desconocido_no_obtiene_acceso_por_claim(self):
        self.rol_actual.return_value = 4
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": {"code": "FORBIDDEN"}})
        self.lista.count.assert_not_called()

    def test_mismo_jwt_observa_retirada_de_membresia(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.rol_actual.return_value = None
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.lista.count.call_count, 1)

    def test_cuenta_deshabilitada_o_con_2fa_es_rechazada(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.cuenta.is_active = False
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.cuenta.is_active = True
        self.cuenta.is_2fa_enabled = True
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.lista.count.call_count, 1)

    def test_fallo_repositorio_es_503_sin_detalles(self):
        self.lista.count.side_effect = OperationalError("synthetic-private-value")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": {"code": "SERVICE_UNAVAILABLE"}})
        self.usuarios.filter.assert_not_called()

    def test_error_inesperado_no_expone_detalles_en_cuerpo_ni_log(self):
        self.lista.count.side_effect = RuntimeError("synthetic-private-value")
        with self.assertLogs("auth_workspaces.errores_organizaciones", level="ERROR") as logs:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": {"code": "INTERNAL_ERROR"}})
        self.assertNotIn("synthetic-private-value", response.content.decode() + "\n".join(logs.output))
        self.assertTrue(all(r.exc_info is None for r in logs.records))

    def test_usuario_relacionado_ausente_no_devuelve_exito_parcial(self):
        self.usuarios.filter.return_value.values.return_value = []
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": {"code": "SERVICE_UNAVAILABLE"}})

    def test_rol_de_fila_invalido_no_tiene_enum_por_defecto(self):
        for nivel in (4, -1, "0", True, None):
            self.fila["nivel_rol"] = nivel
            with self.subTest(nivel=nivel):
                self.assertEqual(self.client.get(self.url).status_code, 503)

    def test_fecha_sin_zona_o_ausente_no_se_fabrica(self):
        for fecha in (FECHA.replace(tzinfo=None), None):
            self.fila["fecha_union"] = fecha
            with self.subTest(fecha=fecha):
                self.assertEqual(self.client.get(self.url).status_code, 503)

    def test_fechas_de_salida_se_normalizan_a_utc(self):
        self.fila["fecha_union"] = FECHA.astimezone(timezone(timedelta(hours=2)))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["fecha_ingreso"], "2026-10-31T12:00:00Z")

    def test_metodos_de_mutacion_no_estan_habilitados(self):
        for method in ("POST", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")
        self.miembros.filter.assert_not_called()

    def test_carga_por_lote_conserva_orden_de_membresias(self):
        self.lista.count.return_value = 2
        self.lista.__getitem__.return_value.values.return_value = [
            {"usuario_id": OTRO_USUARIO, "nivel_rol": 2, "fecha_union": FECHA},
            self.fila,
        ]
        self.usuarios.filter.return_value.values.return_value += [{
            "id": OTRO_USUARIO, "nombre_completo": "Otro miembro",
            "correo_electronico": "another@example.test",
        }]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["usuario_id"] for row in response.json()["results"]], [str(OTRO_USUARIO), str(USUARIO)])
        self.usuarios.filter.assert_called_once_with(pk__in={USUARIO, OTRO_USUARIO})
