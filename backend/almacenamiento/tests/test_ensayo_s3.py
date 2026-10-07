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
        with patch("sys.argv", ["probar_s3", "--ejecutar", "--limpiar-objetos"]), \
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

    def test_navegador_exige_etag_y_preflight(self):
        for etag, preflight in ((False, True), (True, False), (True, True)):
            with self.subTest(etag=etag, preflight=preflight):
                def completo(cliente, claves, informe):
                    for campo in ("put_firmado", "head_tamano_mime", "hash_contenido",
                                  "get_firmado_bytes_exactos", "get_anonimo_denegado",
                                  "copia_bytes_exactos", "get_antes_de_expirar",
                                  "get_expirado_denegado", "put_expirado_denegado"):
                        informe[campo] = True
                    informe["preflight"] = {"aprobado": preflight}
                def navegador(cliente, clave, informe, **kwargs):
                    informe["navegador"] = {"put": True, "get": True, "bytes": True, "etag": etag}
                with patch("sys.argv", ["probar_s3", "--ejecutar", "--navegador", "--limpiar-objetos"]), \
                     patch.object(probar_s3.environ.Env, "read_env"), \
                     patch.object(probar_s3.ConfiguracionS3, "desde_entorno", return_value=configuracion()), \
                     patch.object(probar_s3, "ClienteS3") as clase_cliente, \
                     patch.object(probar_s3, "ensayo", side_effect=completo), \
                     patch.object(probar_s3, "ensayo_navegador", side_effect=navegador), \
                     contextlib.redirect_stdout(StringIO()):
                    clase_cliente.return_value.consultar.side_effect = ErrorS3("ausente")
                    self.assertEqual(probar_s3.main(), 0 if etag and preflight else 1)

    def test_fase8_rechazo_adverso_incompleto_no_certifica_y_limpia(self):
        def completo(cliente, claves, informe):
            for campo in ("put_firmado", "head_tamano_mime", "hash_contenido", "get_firmado_bytes_exactos",
                          "get_anonimo_denegado", "copia_bytes_exactos", "get_antes_de_expirar",
                          "get_expirado_denegado", "put_expirado_denegado"):
                informe[campo] = True
        for adverso in (True, False):
            def seguridad(cliente, claves, informe):
                informe.update(put_header_alterado_denegado=adverso, get_firma_alterada_denegado=True,
                    get_host_alterado_rechazado=True, final_conserva_hash_tras_reuso_put=True)
            with patch("sys.argv", ["probar_s3", "--ejecutar", "--seguridad-fase8", "--limpiar-objetos"]), \
                 patch.object(probar_s3.environ.Env, "read_env"), \
                 patch.object(probar_s3.ConfiguracionS3, "desde_entorno", return_value=configuracion()), \
                 patch.object(probar_s3, "ClienteS3") as clase, \
                 patch.object(probar_s3, "ensayo", side_effect=completo), \
                 patch.object(probar_s3, "ensayo_seguridad", side_effect=seguridad), \
                 contextlib.redirect_stdout(StringIO()):
                clase.return_value.consultar.side_effect = ErrorS3("ausente")
                self.assertEqual(probar_s3.main(), 0 if adverso else 1)
                self.assertEqual(clase.return_value.borrar_tecnico.call_count, 10)

    def test_host_adverso_no_envia_capability_a_otro_endpoint(self):
        cliente = Mock()
        url = "https://s3.example.test/propio?X-Amz-Signature=123&X-Amz-Credential=synthetic"
        cliente.firmar_put.return_value.url = url
        cliente.firmar_put.return_value.encabezados = {"Content-Type": "text/plain"}
        cliente.firmar_get.return_value.url = url
        cliente.verificar_contenido.return_value.sha256 = "0"*64
        informe = {}
        with patch.object(probar_s3, "peticion", side_effect=[(403,b"",{}), (403,b"",{}), (404,b"",{}), (200,b"",{})]) as http:
            probar_s3.ensayo_seguridad(cliente, ["propio-origen", "propio-final"], informe)
        self.assertTrue(all(c.args[0].startswith("https://s3.example.test/") for c in http.call_args_list))
        self.assertEqual(http.call_args_list[2].kwargs["headers"], {"Host": "host-alterado.example.test"})
        self.assertNotIn("X-Amz", json.dumps(informe))
        self.assertTrue(informe["final_conserva_hash_tras_reuso_put"])

    def test_por_defecto_conserva_objetos_sin_delete(self):
        with patch("sys.argv", ["probar_s3", "--ejecutar"]), \
             patch.object(probar_s3.environ.Env, "read_env"), \
             patch.object(probar_s3.ConfiguracionS3, "desde_entorno", return_value=configuracion()), \
             patch.object(probar_s3, "ClienteS3") as clase, \
             patch.object(probar_s3, "ensayo", side_effect=ErrorS3()), \
             contextlib.redirect_stdout(StringIO()) as salida:
            self.assertEqual(probar_s3.main(), 1)
        clase.return_value.borrar_tecnico.assert_not_called()
        informe = json.loads(salida.getvalue())
        self.assertTrue(informe["objetos_conservados_por_instruccion"])
        self.assertFalse(informe["objetos_propios_limpiados"])
        self.assertEqual(len(informe["claves_nuevas_propias"]), 5)
