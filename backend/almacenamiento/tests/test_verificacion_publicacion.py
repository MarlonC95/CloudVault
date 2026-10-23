import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from botocore.exceptions import ClientError
from django.test import SimpleTestCase

from almacenamiento.s3 import ClienteS3, ContenidoS3, ErrorS3, nueva_clave_final, nueva_clave_temporal
from almacenamiento.verificacion import VerificadorSubproceso
from almacenamiento.verificar_publicacion import ejecutar
from .test_s3 import configuracion


class VerificacionPublicacionTests(SimpleTestCase):
    def setUp(self):
        self.clave = nueva_clave_final(uuid4())
        self.sha = hashlib.sha256(b"hola").hexdigest()

    def test_worker_usa_final_limite_exacto_y_cierra_cliente(self):
        cliente = Mock()
        cliente.verificar_contenido.return_value = ContenidoS3(4, self.sha)
        resultado = ejecutar({"clave": self.clave, "tamano_bytes": 4}, cliente_factory=lambda: cliente)
        self.assertEqual(resultado, {"tamano_bytes": 4, "sha256": self.sha})
        cliente.verificar_contenido.assert_called_once_with(self.clave, maximo_bytes=4)
        cliente.cerrar.assert_called_once()

    def test_worker_rechaza_claves_y_limites_antes_de_crear_cliente(self):
        for datos in ({"clave": nueva_clave_temporal(), "tamano_bytes": 4},
                      {"clave": self.clave, "tamano_bytes": True},
                      {"clave": self.clave, "tamano_bytes": 6 << 30},
                      {"clave": self.clave, "tamano_bytes": 4, "secret": "synthetic"}):
            fabrica = Mock()
            with self.assertRaises(ValueError):
                ejecutar(datos, cliente_factory=fabrica)
            fabrica.assert_not_called()

    def test_worker_fallo_cierra_cliente(self):
        cliente = Mock()
        cliente.verificar_contenido.side_effect = ErrorS3("contenido")
        with self.assertRaises(ErrorS3):
            ejecutar({"clave": self.clave, "tamano_bytes": 4}, cliente_factory=lambda: cliente)
        cliente.cerrar.assert_called_once()

    def test_subproceso_real_entrada_invalida_sin_sql_env_o_sdk(self):
        resultado = subprocess.run([sys.executable, "-m", "almacenamiento.verificar_publicacion"],
            cwd=Path(__file__).resolve().parents[2], input='{"secret":"synthetic-private"}',
            text=True, capture_output=True, timeout=10)
        self.assertEqual(resultado.returncode, 1)
        self.assertEqual(json.loads(resultado.stdout), {"error": "servicio"})
        self.assertNotIn("synthetic-private", resultado.stdout + resultado.stderr)

    def test_subproceso_real_hash_por_bloques_con_respuesta_sdk_sintetica(self):
        # Proceso real y algoritmo real; GET sustituido en memoria, sin sockets.
        programa = '''
from io import BytesIO
from unittest.mock import patch
from botocore.response import StreamingBody
from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.s3 import ClienteS3
from almacenamiento.verificar_publicacion import main
cliente = ClienteS3(ConfiguracionS3("railway", "https://s3.example.test", "auto", "bucket-test", "synthetic-access", "synthetic-secret"))
cliente._operar = lambda *args, **kwargs: {"Body": StreamingBody(BytesIO(b"hola"), 4)}
with patch("almacenamiento.verificar_publicacion.ClienteS3", return_value=cliente), patch("almacenamiento.verificar_publicacion.ConfiguracionS3.desde_entorno", return_value=cliente.configuracion):
    raise SystemExit(main())
'''
        resultado = subprocess.run([sys.executable, "-c", programa],
            cwd=Path(__file__).resolve().parents[2],
            input=json.dumps({"clave": self.clave, "tamano_bytes": 4}),
            text=True, capture_output=True, timeout=10)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(json.loads(resultado.stdout), {"tamano_bytes": 4, "sha256": self.sha})

    def test_coordinador_worker_valida_salida_timeout_y_cuerpo(self):
        verificador = VerificadorSubproceso(tiempo_maximo=7)
        respuesta = SimpleNamespace(returncode=0, stdout=json.dumps({"tamano_bytes": 4, "sha256": self.sha}))
        with patch("almacenamiento.verificacion.subprocess.run", return_value=respuesta) as proceso:
            self.assertEqual(verificador(clave=self.clave, tamano_bytes=4), ContenidoS3(4, self.sha))
        opciones = proceso.call_args.kwargs
        self.assertEqual(opciones["timeout"], 7)
        self.assertEqual(json.loads(opciones["input"]), {"clave": self.clave, "tamano_bytes": 4})
        for salida in ('{}', '{"tamano_bytes":true,"sha256":null}', 'invalid',
                       json.dumps({"tamano_bytes": 4, "sha256": "etag"})):
            respuesta.stdout = salida
            with patch("almacenamiento.verificacion.subprocess.run", return_value=respuesta), self.assertRaises(ErrorS3):
                verificador(clave=self.clave, tamano_bytes=4)
        with patch("almacenamiento.verificacion.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 7)), self.assertRaises(ErrorS3):
            verificador(clave=self.clave, tamano_bytes=4)

    def test_worker_tamano_distinto_rechaza_y_error_privado_no_sale(self):
        for salida, tipo in (({"tamano_bytes": 3, "sha256": self.sha}, "contenido"),
                             ({"error": "contenido"}, "contenido"),
                             ({"error": "synthetic-private-error"}, "servicio")):
            respuesta = SimpleNamespace(returncode=0 if "tamano_bytes" in salida else 1,
                                        stdout=json.dumps(salida))
            with patch("almacenamiento.verificacion.subprocess.run", return_value=respuesta), self.assertRaises(ErrorS3) as exc:
                VerificadorSubproceso()(clave=self.clave, tamano_bytes=4)
            self.assertEqual(exc.exception.tipo, tipo)
            self.assertNotIn("synthetic-private", str(exc.exception))

    def test_copy_unico_sdk_sin_retry_metadatos_seguros(self):
        cliente = ClienteS3(configuracion())
        self.addCleanup(cliente.cerrar)
        sdk = Mock()
        sdk.copy_object.return_value = {"CopyObjectResult": {"ETag": '"final"'}}
        with patch("almacenamiento.s3.boto3.session.Session") as sesion:
            sesion.return_value.client.return_value = sdk
            cliente.publicar_una_vez(nueva_clave_temporal(), self.clave, etag_origen='"origen"')
        self.assertEqual(sesion.return_value.client.call_args.kwargs["config"].retries["total_max_attempts"], 1)
        self.assertEqual(sdk.copy_object.call_args.kwargs["ContentType"], "application/octet-stream")
        self.assertEqual(sdk.copy_object.call_args.kwargs["ContentDisposition"], "attachment")
        self.assertEqual(sdk.copy_object.call_args.kwargs["MetadataDirective"], "REPLACE")
        sdk.copy_object.assert_called_once()
        sdk.close.assert_called_once()

    def test_copy_ambiguo_no_repite_ni_consulta_destino(self):
        cliente = ClienteS3(configuracion())
        self.addCleanup(cliente.cerrar)
        sdk = Mock()
        sdk.copy_object.side_effect = ClientError({"Error": {"Code": "InternalError",
                                                 "Message": "synthetic-private"}}, "CopyObject")
        with patch("almacenamiento.s3.boto3.session.Session") as sesion, self.assertRaises(ErrorS3):
            sesion.return_value.client.return_value = sdk
            cliente.publicar_una_vez(nueva_clave_temporal(), self.clave, etag_origen='"origen"')
        sdk.copy_object.assert_called_once()
        sdk.close.assert_called_once()
        sdk.head_object.assert_not_called()
