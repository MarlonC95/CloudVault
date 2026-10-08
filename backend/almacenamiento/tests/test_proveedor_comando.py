"""El diagnóstico verifica interfaz, sin certificar negocio ni ejecutar sus operaciones."""

from io import StringIO
import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from almacenamiento.conexion_negocio import PARAMETROS_PROVEEDOR


class VerificarProveedorTests(SimpleTestCase):
    @override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_proveedor_ausente_no_certifica_integracion_y_falla(self):
        salida = StringIO()
        with self.assertRaises(CommandError):
            call_command("verificar_proveedor_almacenamiento", stdout=salida)
        informe = json.loads(salida.getvalue())
        self.assertFalse(informe["interfaz_compatible"])
        self.assertFalse(informe["integracion_real_verificada"])

    def test_proveedor_valido_no_ejecuta_permisos_registro_cuota_o_s3(self):
        proveedor = SimpleNamespace(using="default", **{n: Mock() for n in PARAMETROS_PROVEEDOR})
        salida = StringIO()
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=lambda: proveedor):
            call_command("verificar_proveedor_almacenamiento", stdout=salida)
        informe = json.loads(salida.getvalue())
        self.assertTrue(informe["interfaz_compatible"])
        self.assertFalse(informe["integracion_real_verificada"])
        self.assertEqual(informe["operaciones_requeridas"], list(PARAMETROS_PROVEEDOR))
        for nombre in PARAMETROS_PROVEEDOR:
            getattr(proveedor, nombre).assert_not_called()

    def test_constructor_fallido_no_revela_error_privado(self):
        salida = StringIO()
        fabrica = Mock(side_effect=RuntimeError("synthetic-private-password"))
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=fabrica), self.assertRaises(CommandError) as error:
            call_command("verificar_proveedor_almacenamiento", stdout=salida)
        self.assertNotIn("synthetic-private", str(error.exception) + salida.getvalue())
