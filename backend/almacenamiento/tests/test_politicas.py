from django.test import SimpleTestCase

from almacenamiento.contrato import PoliticaCarga, ROLES_CON_CAPACIDAD_DE_CARGA


class PoliticasContratoTests(SimpleTestCase):
    def test_valores_iniciales_y_configuracion_local_valida(self):
        defaults = PoliticaCarga()
        self.assertEqual(defaults.maximo_archivo_bytes, 1073741824)
        self.assertEqual(defaults.vigencia_carga_segundos, 900)
        self.assertEqual(defaults.vigencia_descarga_segundos, 300)
        self.assertEqual(PoliticaCarga(maximo_archivo_bytes=1024).maximo_archivo_bytes, 1024)

    def test_configuracion_no_admite_valores_que_debiliten_ttl_o_rompan_sql(self):
        for campo, valor in (
            ("maximo_archivo_bytes", 0), ("maximo_archivo_bytes", True),
            ("maximo_archivo_bytes", 1 << 63), ("maximo_archivo_bytes", "1024"),
            ("vigencia_carga_segundos", 901), ("vigencia_carga_segundos", -1),
            ("vigencia_descarga_segundos", 301), ("vigencia_descarga_segundos", 0),
        ):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                PoliticaCarga(**{campo: valor})

    def test_propietario_cero_incluido_lector_uno_excluido(self):
        self.assertIn(0, ROLES_CON_CAPACIDAD_DE_CARGA)
        self.assertNotIn(1, ROLES_CON_CAPACIDAD_DE_CARGA)
        self.assertEqual(ROLES_CON_CAPACIDAD_DE_CARGA, {0, 2, 3})
