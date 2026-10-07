"""El diagnóstico real es de lectura; errores e informes no exponen secretos."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
import psycopg

from almacenamiento import verificar_entorno_real
from almacenamiento.tests_persistencia import ejecutar_s3_local


class EntornoRealTests(SimpleTestCase):
    def ejecutar(self, conexion):
        entorno = {"DB_HOST": "localhost", "DB_NAME": "synthetic", "DB_USER": "synthetic",
                   "DB_PASSWORD": "synthetic-private-password"}
        with patch("sys.argv", ["verificar", "--informe", "/private/tmp/no-escrito.json"]), \
             patch.dict(verificar_entorno_real.os.environ, entorno, clear=True), \
             patch.object(verificar_entorno_real.environ.Env, "read_env"), \
             patch.object(verificar_entorno_real.ConfiguracionS3, "desde_entorno"), \
             patch.object(verificar_entorno_real.Path, "read_bytes", return_value=b"synthetic-private-env"), \
             patch.object(verificar_entorno_real.Path, "read_text", return_value="CREATE TABLE IF NOT EXISTS usuarios (id UUID);"), \
             patch.object(verificar_entorno_real.Path, "write_text") as guardar, \
             patch.object(verificar_entorno_real.psycopg, "connect", side_effect=conexion) as conectar, \
             redirect_stdout(StringIO()):
            estado = verificar_entorno_real.main()
        return estado, json.loads(guardar.call_args.args[0]), conectar

    def test_conexion_fuerza_solo_lectura_y_consulta_unicamente_metadatos(self):
        conn = Mock()
        conn.info.server_version = 180006
        def consultar(sql, *args):
            respuesta = Mock()
            respuesta.fetchone.return_value = ("on",) if sql.startswith("SHOW") else (True,)
            return respuesta
        conn.execute.side_effect = consultar
        contexto = Mock()
        contexto.__enter__ = Mock(return_value=conn)
        contexto.__exit__ = Mock(return_value=False)
        estado, informe, conectar = self.ejecutar(lambda **kwargs: contexto)
        self.assertEqual(estado, 0)
        self.assertIn("default_transaction_read_only=on", conectar.call_args.kwargs["options"])
        self.assertTrue(all(c.args[0].lstrip().startswith(("SELECT", "SHOW")) for c in conn.execute.call_args_list))
        self.assertTrue(informe["env_sin_cambios"])
        self.assertNotIn("synthetic-private", json.dumps(informe))

    def test_fallo_privado_no_se_escribe_en_informe(self):
        estado, informe, _ = self.ejecutar(Mock(side_effect=psycopg.OperationalError("synthetic-private-password")))
        self.assertEqual(estado, 1)
        self.assertFalse(informe["sql_conectado"])
        self.assertEqual(informe["fallo_sql_tipo"], "OperationalError")
        self.assertNotIn("synthetic-private", json.dumps(informe))

    def test_controlador_con_limpieza_exige_autorizacion_antes_de_docker(self):
        with patch("sys.argv", ["controlador", "--directorio-informes", "/private/tmp"]), \
             patch.object(ejecutar_s3_local.shutil, "which") as docker, \
             redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            ejecutar_s3_local.main()
        docker.assert_not_called()
