from io import StringIO
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from almacenamiento.configuracion_mantenimiento import PoliticaMantenimiento, politica_mantenimiento
from almacenamiento.errores import ErrorCarga


class MantenimientoSinDBTests(SimpleTestCase):
    def test_politica_rechaza_limites_invalidos(self):
        for cambio in ({"margen_segundos": 0}, {"barrido_segundos": True},
                       {"reintento_segundos": 4000}, {"lote": 1001},
                       {"reintento_maximo_segundos": 86401}):
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                PoliticaMantenimiento(**cambio)

    def test_configuracion_invalida_no_cae_a_defaults(self):
        with override_settings(ALMACENAMIENTO_MARGEN_LIMPIEZA_SEGUNDOS="secret-invalid"):
            with self.assertRaises(ErrorCarga):
                politica_mantenimiento()

    def test_comando_una_ejecucion_publica_solo_metricas(self):
        salida = StringIO()
        servicio = SimpleNamespace(ejecutar=Mock(return_value={"procesados": 0, "metricas": {}}))
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento",
                   return_value=servicio):
            call_command("mantener_cargas", stdout=salida)
        servicio.ejecutar.assert_called_once()
        self.assertIn('"ciclo": 1', salida.getvalue())

    def test_errores_del_comando_no_muestran_secretos(self):
        servicio = SimpleNamespace(ejecutar=Mock(side_effect=RuntimeError("synthetic-private-url-secret")))
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento",
                   return_value=servicio), self.assertRaises(CommandError) as error:
            call_command("mantener_cargas")
        self.assertNotIn("secret", str(error.exception))

    def test_registro_de_ciclo_tiene_fecha_duracion_y_nivel_de_incidencia(self):
        salida = StringIO()
        servicio = SimpleNamespace(ejecutar=Mock(return_value={
            "procesados": 1, "resultados": {"INTEGRIDAD": 1}, "metricas": {}}))
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento",
                   return_value=servicio), patch(
                       "almacenamiento.management.commands.mantener_cargas.time.monotonic",
                       side_effect=[10, 12.5]):
            call_command("mantener_cargas", stdout=salida)
        registro = json.loads(salida.getvalue())
        self.assertIsNotNone(datetime.fromisoformat(registro["fecha_utc"]).tzinfo)
        self.assertEqual(registro["duracion_segundos"], 2.5)
        self.assertEqual(registro["level"], "warn")
        self.assertEqual(registro["evento"], "mantenimiento_ciclo")

    def test_fallo_de_ciclo_unico_registra_error_antes_de_salir(self):
        salida = StringIO()
        servicio = SimpleNamespace(ejecutar=Mock(side_effect=RuntimeError("synthetic-private-secret")))
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento",
                   return_value=servicio), self.assertRaises(CommandError):
            call_command("mantener_cargas", stdout=salida)
        registro = json.loads(salida.getvalue())
        self.assertEqual(registro["level"], "error")
        self.assertEqual(registro["error"], "SERVICE_UNAVAILABLE")
        self.assertNotIn("secret", salida.getvalue())

    def test_parametros_invalidos_no_inician_servicio(self):
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento") as fabrica:
            for opciones in ({"intervalo": 0}, {"intervalo": 4000}, {"ciclos": 0}, {"ciclos": 2}):
                with self.subTest(opciones=opciones), self.assertRaises(CommandError):
                    call_command("mantener_cargas", **opciones)
            fabrica.assert_not_called()

    def test_periodico_reintenta_dependencia_sin_terminar(self):
        servicio = SimpleNamespace(ejecutar=Mock(side_effect=[
            RuntimeError("synthetic-private-secret"), {"procesados": 0}]))
        salida = StringIO()
        with patch("almacenamiento.management.commands.mantener_cargas.crear_servicio_mantenimiento",
                   return_value=servicio), patch("almacenamiento.management.commands.mantener_cargas.time.sleep"):
            call_command("mantener_cargas", continuo=True, ciclos=2, stdout=salida)
        self.assertEqual(servicio.ejecutar.call_count, 2)
        self.assertIn("SERVICE_UNAVAILABLE", salida.getvalue())
        self.assertNotIn("secret", salida.getvalue())
