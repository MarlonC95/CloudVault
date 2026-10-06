"""El ensayo nunca certifica éxito parcial y limpia solo sus propias claves."""

import contextlib
from io import StringIO
import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from almacenamiento import probar_s3
from almacenamiento.s3 import ErrorS3
from .test_s3 import configuracion


class EnsayoTests(SimpleTestCase):
    def ejecutar(self, accion):
        cliente = Mock()
        cliente.consultar.side_effect = ErrorS3("ausente")
        salida = StringIO()
        with patch("sys.argv", ["probar_s3", "--ejecutar"]), \
             patch.object(probar_s3.environ.Env, "read_env"), \
             patch.object(probar_s3.ConfiguracionS3, "desde_entorno", return_value=configuracion()), \
             patch.object(probar_s3, "ClienteS3", return_value=cliente), \
             patch.object(probar_s3, "ensayo", side_effect=accion), \
             contextlib.redirect_stdout(salida):
            estado = probar_s3.main()
        return estado, json.loads(salida.getvalue()), cliente

    def test_no_ejecuta_red_por_defecto(self):
        with patch("sys.argv", ["probar_s3"]), patch.object(probar_s3, "ClienteS3") as cliente, \
             contextlib.redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            probar_s3.main()
        cliente.assert_not_called()

    def test_fallo_parcial_limpia_todas_sus_claves_y_no_expone_error(self):
        def fallo(*args):
            raise RuntimeError("synthetic-private-url")
        estado, informe, cliente = self.ejecutar(fallo)
        self.assertEqual(estado, 1)
        self.assertTrue(informe["objetos_propios_limpiados"])
        self.assertEqual(cliente.borrar_tecnico.call_count, 10)
        self.assertNotIn("synthetic-private-url", str(informe))
        claves = {call.args[0] for call in cliente.borrar_tecnico.call_args_list}
        self.assertEqual(len(claves), 5)
        self.assertTrue(all(clave.startswith("cloudvault/dani/pruebas/" + informe["prueba"] + "/") for clave in claves))

    def test_booleano_negativo_no_certifica_flujo(self):
        def parcial(cliente, claves, informe):
            informe["put_firmado"] = False
        estado, informe, cliente = self.ejecutar(parcial)
        self.assertEqual(estado, 1)
        self.assertFalse(informe["put_firmado"])

    def test_borrado_sin_confirmar_ausencia_no_certifica_limpieza(self):
        def parcial(cliente, claves, informe):
            cliente.consultar.side_effect = ErrorS3("acceso")
        estado, informe, cliente = self.ejecutar(parcial)
        self.assertEqual(estado, 1)
        self.assertFalse(informe["objetos_propios_limpiados"])

    def test_flujo_completo_tiene_exit_cero_sin_exigir_capacidades_opcionales(self):
        def completo(cliente, claves, informe):
            for nombre in ("put_firmado", "head_tamano_mime", "hash_contenido", "get_firmado_bytes_exactos",
                           "get_anonimo_denegado", "copia_bytes_exactos", "get_antes_de_expirar",
                           "get_expirado_denegado", "put_expirado_denegado"):
                informe[nombre] = True
            informe["checksum_sha256_retornado"] = False
        estado, informe, cliente = self.ejecutar(completo)
        self.assertEqual(estado, 0)
        cliente.cerrar.assert_called_once()
