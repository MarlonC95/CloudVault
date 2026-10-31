from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.http import QueryDict
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from auth_workspaces.contratos_auditoria import (
    AuditoriaNoDisponible, detalles_publicos, filtros_auditoria, proyectar_evento,
)


CORTE = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
ORG = UUID("b0000000-0000-4000-8000-000000000001")
USUARIO = UUID("a0000000-0000-4000-8000-000000000001")
RECURSO = UUID("c0000000-0000-4000-8000-000000000001")


class FiltrosAuditoriaTests(SimpleTestCase):
    def filtros(self, datos=None):
        query = QueryDict("", mutable=True)
        query.update(datos or {})
        return filtros_auditoria(query, corte=CORTE)

    def test_ventana_por_defecto_y_paginacion(self):
        filtros = self.filtros()
        self.assertEqual((filtros.page, filtros.page_size), (1, 50))
        self.assertEqual(filtros.hasta, CORTE)
        self.assertEqual(filtros.desde, CORTE - timedelta(days=30))
        self.assertIsNone(filtros.usuario_id)
        self.assertIsNone(filtros.accion)

    def test_fechas_parciales_y_zonas_se_normalizan(self):
        hasta = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        filtros = self.filtros({"hasta": "2026-10-20T14:00:00+02:00"})
        self.assertEqual(filtros.hasta, hasta)
        self.assertEqual(filtros.desde, hasta - timedelta(days=30))
        filtros = self.filtros({"desde": "2026-10-01T12:00:00Z"})
        self.assertEqual(filtros.hasta, CORTE)
        self.assertEqual(filtros.desde, datetime(2026, 10, 1, 12, tzinfo=timezone.utc))

    def test_limite_exacto_de_366_dias(self):
        filtros = self.filtros({"desde": (CORTE - timedelta(days=366)).isoformat()})
        self.assertEqual(filtros.hasta - filtros.desde, timedelta(days=366))
        with self.assertRaises(ValidationError):
            self.filtros({"desde": (CORTE - timedelta(days=366, microseconds=1)).isoformat()})

    def test_intervalos_vacios_invertidos_o_demasiado_largos(self):
        for desde in (CORTE, CORTE + timedelta(days=1), CORTE - timedelta(days=367)):
            with self.subTest(desde=desde), self.assertRaises(ValidationError):
                self.filtros({"desde": desde.isoformat()})

    def test_fechas_sin_zona_invalidas_o_fuera_de_rango(self):
        for valor in ("", "null", "2026-10-01", "2026-10-01T12:00:00", "2026-02-30T12:00:00Z"):
            for campo in ("desde", "hasta"):
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                    self.filtros({campo: valor})
        with self.assertRaises(ValidationError):
            self.filtros({"hasta": "0001-01-01T00:00:00Z"})

    def test_usuario_y_accion_estrictos_recortados(self):
        filtros = self.filtros({"usuario_id": str(USUARIO), "accion": " PAPELERA_PURGADO "})
        self.assertEqual(filtros.usuario_id, USUARIO)
        self.assertEqual(filtros.accion, "PAPELERA_PURGADO")
        for campo, valor in (("usuario_id", ""), ("usuario_id", "not-a-uuid"), ("accion", " "), ("accion", "a" * 101)):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                self.filtros({campo: valor})
        self.assertEqual(len(self.filtros({"accion": "a" * 100}).accion), 100)

    def test_repetidos_extras_y_override_de_organizacion(self):
        for query in ("page=1&page=2", "accion=A&accion=A", "desde=x&desde=x", f"organizacion_id={ORG}", "buscar=x"):
            with self.subTest(query=query), self.assertRaises(ValidationError):
                filtros_auditoria(QueryDict(query), corte=CORTE)

    def test_enteros_y_tamano_de_pagina(self):
        self.assertEqual(self.filtros({"page_size": "100"}).page_size, 100)
        for nombre, valor in (("page", "0"), ("page", "1.5"), ("page", "true"), ("page", "-1"), ("page_size", "101"), ("page_size", "")):
            with self.subTest(nombre=nombre, valor=valor), self.assertRaises(ValidationError):
                self.filtros({nombre: valor})

    def test_corte_excluye_futuro_sin_cambiar_ventana_solicitada(self):
        hasta = CORTE + timedelta(days=1)
        filtros = self.filtros({"hasta": hasta.isoformat()})
        self.assertEqual(filtros.hasta, hasta)
        self.assertEqual(filtros.fin_lectura, CORTE)
        pasado = self.filtros({"hasta": (CORTE - timedelta(days=1)).isoformat()})
        self.assertEqual(pasado.fin_lectura, pasado.hasta)

    def test_reloj_no_consciente_falla_sin_inventar_zona(self):
        with self.assertRaises(AuditoriaNoDisponible):
            filtros_auditoria(QueryDict(), corte=CORTE.replace(tzinfo=None))


class ProyeccionAuditoriaTests(SimpleTestCase):
    def fila(self, **cambios):
        return {
            "id": 17, "organizacion_id": ORG, "usuario_id": USUARIO,
            "accion": "PAPELERA_PURGADO", "fecha_evento": CORTE,
            "detalles": {"recurso_id": str(RECURSO), "tipo_elemento": "archivo", "bytes_fisicos_purgados": 80},
            **cambios,
        }

    def test_salida_exacta_y_allowlist_real_de_purga(self):
        fila = self.fila(ip_origen="synthetic-private-value")
        fila["detalles"].update({
            "clave_s3": "synthetic-private-value", "token": "synthetic-private-value",
            "generacion_id": str(RECURSO), "operacion_id": str(RECURSO),
            "miembros": [{"password": "synthetic-private-value"}],
        })
        original = deepcopy(fila)
        salida = proyectar_evento(fila)
        self.assertEqual(salida, {
            "id": 17, "organizacion_id": str(ORG), "usuario_id": str(USUARIO),
            "accion": "PAPELERA_PURGADO", "fecha_evento": "2026-10-31T12:00:00Z",
            "detalles": {"recurso_id": str(RECURSO), "tipo_elemento": "archivo", "bytes_fisicos_purgados": 80},
        })
        self.assertNotIn("synthetic-private-value", str(salida))
        self.assertEqual(fila, original)

    def test_desconocida_o_json_no_objeto_producen_detalles_vacios(self):
        for accion in ("FUTURA", None, []):
            self.assertEqual(detalles_publicos(accion, {"recurso_id": str(RECURSO), "token": "synthetic"}), {})
        for detalles in (None, [], "synthetic", 1):
            self.assertEqual(detalles_publicos("PAPELERA_PURGADO", detalles), {})

    def test_valores_maliciosos_no_pasan_por_tener_clave_permitida(self):
        for valor in ({"token": "synthetic"}, [str(RECURSO)], "https://example.test/signed?token=synthetic", True, None):
            self.assertEqual(detalles_publicos("PAPELERA_PURGADO", {"recurso_id": valor}), {})
        for valor in (True, -1, "80", 1.5, 2**63):
            self.assertEqual(detalles_publicos("PAPELERA_PURGADO", {"bytes_fisicos_purgados": valor}), {})
        self.assertEqual(detalles_publicos("PAPELERA_PURGADO", {"tipo_elemento": "synthetic-secret"}), {})

    def test_carpeta_no_filtra_manifiestos_ni_motivos(self):
        salida = detalles_publicos("PAPELERA_CARPETA_ENVIADA", {
            "raiz_id": str(RECURSO), "miembros": [{"clave_s3": "synthetic"}],
            "motivo": "synthetic-private-value", "raiz_generacion_id": str(RECURSO),
        })
        self.assertEqual(salida, {"raiz_id": str(RECURSO)})
        self.assertEqual(detalles_publicos("USER_STATUS_CHANGED", {"motivo": "synthetic-private-value"}), {})

    def test_admin_data_accedida_tiene_version_y_valores_cerrados(self):
        detalles = {"version": 1, "operacion": "AUDITORIA_ORGANIZACION", "filtro_accion": False, "usuario_filtro_id": str(USUARIO), "ip": "synthetic"}
        self.assertEqual(detalles_publicos("ADMIN_DATA_ACCESSED", detalles), {
            "operacion": "AUDITORIA_ORGANIZACION", "filtro_accion": False, "usuario_filtro_id": str(USUARIO),
        })
        for version in (None, True, 2):
            self.assertEqual(detalles_publicos("ADMIN_DATA_ACCESSED", {**detalles, "version": version}), {})
        self.assertEqual(detalles_publicos("ADMIN_DATA_ACCESSED", {"version": 1, "operacion": "https://example.test/secret", "filtro_accion": "false"}), {})

    def test_nulos_contractuales_y_fecha_en_utc(self):
        salida = proyectar_evento(self.fila(organizacion_id=None, usuario_id=None,
            fecha_evento=CORTE.astimezone(timezone(timedelta(hours=2)))))
        self.assertIsNone(salida["organizacion_id"])
        self.assertIsNone(salida["usuario_id"])
        self.assertEqual(salida["fecha_evento"], "2026-10-31T12:00:00Z")

    def test_fila_incompleta_o_inconsistente_no_se_fabrica(self):
        for campo, valor in (("id", True), ("id", 0), ("id", str(RECURSO)), ("organizacion_id", "invalid"), ("accion", None), ("accion", "a" * 101), ("fecha_evento", CORTE.replace(tzinfo=None))):
            with self.subTest(campo=campo), self.assertRaises(AuditoriaNoDisponible):
                proyectar_evento(self.fila(**{campo: valor}))
        fila = self.fila()
        del fila["detalles"]
        with self.assertRaises(AuditoriaNoDisponible):
            proyectar_evento(fila)
