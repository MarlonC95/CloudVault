"""El reporte no debe convertir ausencia, fallo o doble en integración verde."""

import json
from io import StringIO
import unittest

from django.test import SimpleTestCase

from almacenamiento.tests_persistencia.aceptacion import MATRIZ, combinar_minio, combinar_railway, crear_informe
from almacenamiento.tests_persistencia.runner import ResultadoConEvidencia


class InformeAceptacionTests(SimpleTestCase):
    def resultados(self):
        return [{"id": t, "estado": "APROBADO", "segundos": 0.01,
                 "traceback": "synthetic-private-url?X-Amz-Signature=private"}
                for t in dict.fromkeys(t for fila in MATRIZ for t in fila[-1])]

    def informe(self, resultados=None, **kwargs):
        return crear_informe(self.resultados() if resultados is None else resultados,
                             {"reinicio_postgresql_verificado": True}, salida=kwargs.get("salida", 0),
                             limpio=kwargs.get("limpio", True))

    def test_matriz_completa_ids_unicos_y_expectativas_de_estado(self):
        esperados = {f"{prefijo}{i:02d}" for prefijo, n in (("A",17),("B",5),("C",12),("D",5),("E",6),("F",4)) for i in range(1,n+1)}
        self.assertEqual({f[0] for f in MATRIZ}, esperados)
        self.assertEqual(len(MATRIZ), 49)
        for fila in MATRIZ:
            self.assertTrue(all(fila[i] for i in range(1, 7)))

    def test_aprobados_locales_no_certifican_s3_ni_auth_real(self):
        informe = self.informe()
        self.assertTrue(informe["ejecucion_local_aprobada"])
        self.assertFalse(informe["integracion_completa_certificada"])
        for caso in informe["matriz"]:
            self.assertEqual(caso["integracion_equipo"], "BLOQUEADO")
            if caso["id"] in ("B01", "B02", "B04", "B05", "F03"):
                self.assertEqual(caso["estado_local"], "BLOQUEADO")

    def test_prueba_faltante_skip_y_fallo_no_pasan_por_inferencia(self):
        for estado, esperado in (("BLOQUEADO", "BLOQUEADO"), ("FALLIDO", "FALLIDO"), (None, "BLOQUEADO")):
            resultados = self.resultados()
            prueba = resultados[0]
            if estado is None:
                resultados.pop(0)
            else:
                prueba["estado"] = estado
            informe = self.informe(resultados)
            self.assertEqual(informe["matriz"][0]["estado_local"], esperado)
            self.assertFalse(informe["ejecucion_local_aprobada"])
            self.assertNotIn("synthetic-private", json.dumps(informe))

    def test_salida_no_cero_cluster_no_limpiado_y_suite_vacia_no_aprueban(self):
        for informe in (self.informe(salida=1), self.informe(limpio=False), self.informe([])):
            self.assertFalse(informe["ejecucion_local_aprobada"])

    def test_conservacion_deliberada_no_se_reporta_como_borrado(self):
        informe = crear_informe(self.resultados(), {"temporales_conservados_por_instruccion": True}, salida=0, limpio=False)
        self.assertTrue(informe["ejecucion_local_aprobada"])
        self.assertFalse(informe["cluster_temporal_eliminado"])
        self.assertTrue(informe["temporales_conservados_por_instruccion"])

    def test_reinicio_sin_evidencia_no_aprueba_f04(self):
        informe = crear_informe(self.resultados(), {}, salida=0, limpio=True)
        self.assertEqual(next(c for c in informe["matriz"] if c["id"] == "F04")["estado_local"], "BLOQUEADO")

    def test_colector_conserva_subtests_fallidos_y_omitidos_sin_razones_privadas(self):
        class CasosDeEnsayo(unittest.TestCase):
            def test_omitido(self):
                with self.subTest():
                    self.skipTest("synthetic-private-skip")

            def test_fallido(self):
                with self.subTest():
                    self.fail("synthetic-private-error")

        resultado = unittest.TextTestRunner(stream=StringIO(), resultclass=ResultadoConEvidencia).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(CasosDeEnsayo))
        self.assertEqual([r["estado"] for r in resultado.evidencia], ["FALLIDO", "BLOQUEADO"])
        self.assertNotIn("synthetic-private", json.dumps(resultado.evidencia))

    def test_combinar_no_admite_evidencia_parcial_otro_perfil_o_navegador_ausente(self):
        control = {"salida_sql_s3": 0, "salida_s3": 0, "contenedor_eliminado": True, "datos_minio_eliminados": True}
        s3 = {"perfil": "minio", "objetos_propios_limpiados": True, "put_firmado": True,
              "head_tamano_mime": True, "hash_contenido": True}
        for perfil, limpieza in (("minio", True), ("railway", True), ("minio", False)):
            combinado = combinar_minio(self.informe(), {**s3, "perfil": perfil, "objetos_propios_limpiados": limpieza}, control)
            casos = {c["id"]: c for c in combinado["matriz"]}
            self.assertEqual(casos["B01"]["estado_fase8"], "APROBADO_S3_LOCAL" if perfil == "minio" and limpieza else "BLOQUEADO")
            for codigo in ("B02", "B04", "B05", "F03", "F04"):
                self.assertEqual(casos[codigo]["estado_fase8"], "BLOQUEADO")
            self.assertFalse(combinado["integracion_completa_certificada"])

    def test_railway_conservado_certifica_operaciones_sin_afirmar_limpieza_o_despliegue(self):
        s3 = {"perfil": "railway", "operaciones_aprobadas": True, "put_firmado": True,
              "head_tamano_mime": True, "hash_contenido": True, "objetos_conservados_por_instruccion": True}
        informe = combinar_railway(self.informe(), s3, {"env_sin_cambios": True}, {})
        casos = {c["id"]: c for c in informe["matriz"]}
        self.assertEqual(casos["B01"]["estado_fase8"], "APROBADO_RAILWAY")
        self.assertEqual(casos["B02"]["estado_fase8"], "BLOQUEADO")
        self.assertEqual(casos["F03"]["estado_fase8"], "BLOQUEADO")
        self.assertEqual(casos["F04"]["estado_fase8"], "BLOQUEADO")
        self.assertTrue(informe["objetos_conservados_por_instruccion"])
        self.assertFalse(informe["integracion_completa_certificada"])

    def test_regresion_auth_necesita_exito_y_perfil_observado(self):
        for perfil in (None, "AUTH_COMPAT_FECHA_OBSERVADA"):
            informe = combinar_railway(self.informe(), {}, {}, {"regresion_auth_aprobada": True, "ambiente": {"perfil": perfil}})
            caso = next(c for c in informe["matriz"] if c["id"] == "F03")
            self.assertEqual(caso["estado_fase8"], "APROBADO_AUTH_COMPAT_LOCAL" if perfil else "BLOQUEADO")
