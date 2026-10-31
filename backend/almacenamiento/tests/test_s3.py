"""Firmas reales offline y errores/lecturas con respuestas SDK controladas."""

import hashlib
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from django.test import SimpleTestCase

from almacenamiento.configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida
from almacenamiento.contrato import CodigoError
from almacenamiento.s3 import ClienteS3, ErrorS3, nueva_clave_final, nueva_clave_temporal


def configuracion(**kwargs):
    return ConfiguracionS3(**{**dict(perfil="railway", endpoint="https://s3.example.test",
                                    region="auto", bucket="bucket-pruebas",
                                    access_key="synthetic-access", secret_key="synthetic-secret"), **kwargs})


class ConfiguracionTests(SimpleTestCase):
    def test_perfiles_no_mezclan_credenciales_ni_bucket(self):
        env = {"AWS_ENDPOINT_URL": "https://s3.example.test", "AWS_REGION": "auto",
               "AWS_STORAGE_BUCKET_NAME": "bucket-pruebas", "AWS_ACCESS_KEY_ID": "synthetic-access",
               "AWS_SECRET_ACCESS_KEY": "synthetic-secret", "S3_BUCKET": "otro-bucket"}
        self.assertEqual(ConfiguracionS3.desde_entorno(env).bucket, "bucket-pruebas")
        with self.assertRaises(ConfiguracionS3Invalida):
            ConfiguracionS3.desde_entorno(env, perfil="minio")

    def test_perfil_y_variables_faltantes(self):
        for perfil in ("railway", "minio", "invalido"):
            with self.subTest(perfil=perfil), self.assertRaises(ConfiguracionS3Invalida):
                ConfiguracionS3.desde_entorno({}, perfil=perfil)

    def test_endpoint_invalido_y_tls_obligatorio_remoto(self):
        for endpoint in ("http://example.test", "https://user:secret@example.test", "https://example.test/path",
                         "https://example.test?secret=1", "https://example.test#x", "https://example.test:xyz", ""):
            with self.subTest(endpoint=endpoint), self.assertRaises(ConfiguracionS3Invalida):
                configuracion(endpoint=endpoint)

    def test_minio_puede_separar_endpoint_interno_y_publico(self):
        config = configuracion(perfil="minio", endpoint="http://minio:9000",
                               endpoint_firma="http://localhost:9000", estilo="path")
        self.assertEqual(config.endpoint_firma, "http://localhost:9000")
        with self.assertRaises(ConfiguracionS3Invalida):
            configuracion(endpoint_firma="https://otro.example.test")

    def test_no_imprime_credenciales_en_repr_ni_error(self):
        self.assertNotIn("synthetic-secret", repr(configuracion()))
        self.assertNotIn("synthetic-access", repr(configuracion()))
        with self.assertRaises(ConfiguracionS3Invalida) as exc:
            configuracion(secret_key="valor privado")
        self.assertNotIn("valor privado", str(exc.exception))

    def test_rechaza_estilo_bucket_y_credenciales_invalidos(self):
        for kwargs in ({"estilo": "auto"}, {"bucket": "bad/bucket"}, {"access_key": ""}, {"region": "a b"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfiguracionS3Invalida):
                configuracion(**kwargs)


class ClienteTests(SimpleTestCase):
    def setUp(self):
        self.cliente = ClienteS3(configuracion())
        self.addCleanup(self.cliente.cerrar)
        self.temporal = nueva_clave_temporal()
        self.final = nueva_clave_final(uuid4())

    def test_firma_put_sigv4_clave_content_type_ttl(self):
        firma = self.cliente.firmar_put(self.temporal, "application/pdf")
        url = urlsplit(firma.url)
        query = parse_qs(url.query)
        self.assertEqual(url.hostname, "bucket-pruebas.s3.example.test")
        self.assertEqual(url.path, "/" + self.temporal)
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertEqual(query["X-Amz-SignedHeaders"], ["content-type;host"])
        self.assertEqual(query["X-Amz-Expires"], ["900"])
        self.assertEqual(firma.encabezados, {"Content-Type": "application/pdf"})
        self.assertEqual(firma.metodo, "PUT")
        self.assertNotIn(firma.url, repr(firma))

    def test_firma_get_permite_clave_negocio_sin_alterarla(self):
        firma = self.cliente.firmar_get("archivos/documento.pdf")
        self.assertEqual(parse_qs(urlsplit(firma.url).query)["X-Amz-Expires"], ["300"])
        self.assertEqual(firma.encabezados, {})

    def test_minio_firma_host_publico_path_style(self):
        cliente = ClienteS3(configuracion(perfil="minio", endpoint="http://minio:9000",
                                          endpoint_firma="http://localhost:9000", estilo="path"))
        self.addCleanup(cliente.cerrar)
        url = urlsplit(cliente.firmar_put(self.temporal, "text/plain").url)
        self.assertEqual(url.netloc, "localhost:9000")
        self.assertEqual(url.path, "/bucket-pruebas/" + self.temporal)

    def test_rechaza_put_sobre_publicacion_o_clave_ajena(self):
        for clave in (self.final, "archivos/documento.pdf", "cloudvault/dani/temporales/../otro"):
            with self.subTest(clave=clave), self.assertRaises(ValueError):
                self.cliente.firmar_put(clave, "text/plain")

    def test_ttl_y_mime_invalidos(self):
        for ttl in (True, 0, -1, 901, "30"):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                self.cliente.firmar_put(self.temporal, "text/plain", vigencia=ttl)
        for mime in ("text", "text/plain\n", "text/plain\r\nx-secret: value"):
            with self.subTest(mime=mime), self.assertRaises(ValueError):
                self.cliente.firmar_put(self.temporal, mime)

    def test_consulta_y_checksum_no_se_confunden_con_etag(self):
        with Stubber(self.cliente._cliente) as stub:
            stub.add_response("head_object", {"ContentLength": 4, "ETag": '"abcd"',
                                               "ContentType": "text/plain", "ChecksumSHA256": "base64=="},
                              {"Bucket": "bucket-pruebas", "Key": self.temporal})
            objeto = self.cliente.consultar(self.temporal)
        self.assertEqual(objeto.tamano_bytes, 4)
        self.assertEqual(objeto.checksum_sha256, "base64==")
        self.assertIsNone(objeto.version)

    def test_404_difiere_de_403_y_error_no_expone_xml(self):
        for codigo, tipo in (("404", "ausente"), ("AccessDenied", "acceso"), ("PreconditionFailed", "precondicion"), ("InternalError", "servicio")):
            with self.subTest(codigo=codigo), Stubber(self.cliente._cliente) as stub:
                stub.add_client_error("head_object", service_error_code=codigo,
                                      service_message="private-secret-url-and-xml")
                with self.assertRaises(ErrorS3) as exc:
                    self.cliente.consultar(self.temporal)
                self.assertEqual(exc.exception.tipo, tipo)
                self.assertNotIn("private-secret", str(exc.exception))
                self.assertEqual(exc.exception.codigo, CodigoError.NO_ENCONTRADO if tipo == "ausente" else CodigoError.SERVICE_UNAVAILABLE)

    def test_timeout_seguro(self):
        with patch.object(self.cliente._cliente, "head_object", side_effect=EndpointConnectionError(endpoint_url="https://secret.example")):
            with self.assertRaises(ErrorS3) as exc:
                self.cliente.consultar(self.temporal)
        self.assertNotIn("secret.example", str(exc.exception))

    def test_copia_condicional_y_verificacion_head(self):
        with Stubber(self.cliente._cliente) as stub:
            stub.add_response("copy_object", {"CopyObjectResult": {"ETag": '"resultado"'}},
                              {"Bucket": "bucket-pruebas", "Key": self.final,
                               "CopySource": {"Bucket": "bucket-pruebas", "Key": self.temporal},
                               "CopySourceIfMatch": '"origen"'})
            stub.add_response("head_object", {"ETag": '"resultado"', "ContentLength": 4})
            self.assertEqual(self.cliente.copiar(self.temporal, self.final, etag_origen='"origen"').tamano_bytes, 4)

    def test_copia_200_sin_resultado_no_es_exito(self):
        with Stubber(self.cliente._cliente) as stub:
            stub.add_response("copy_object", {})
            with self.assertRaises(ErrorS3):
                self.cliente.copiar(self.temporal, self.final, etag_origen='"origen"')

    def test_no_copia_o_borra_claves_ajenas(self):
        with self.assertRaises(ValueError):
            self.cliente.copiar("archivos/otro.pdf", self.final, etag_origen='"x"')
        with self.assertRaises(ValueError):
            self.cliente.borrar_tecnico("archivos/otro.pdf")
        with self.assertRaises(ValueError):
            self.cliente.copiar(self.temporal, self.temporal, etag_origen='"x"')

    def test_borrado_idempotente(self):
        with Stubber(self.cliente._cliente) as stub:
            stub.add_response("delete_object", {})
            stub.add_response("delete_object", {})
            self.cliente.borrar_tecnico(self.temporal)
            self.cliente.borrar_tecnico(self.temporal)

    def test_borrado_fisico_elimina_versiones_de_clave_exacta_y_verifica(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=[
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
        ]) as operar:
            self.cliente.borrar_fisico_verificado(clave)
        self.assertEqual(operar.call_args_list[0].args, ("get_bucket_versioning",))
        self.assertEqual(operar.call_args_list[1].kwargs, {"Prefix": clave, "MaxKeys": 1000})
        self.assertEqual(operar.call_args_list[2].kwargs, {"Key": clave})
        self.assertEqual(operar.call_args_list[3].kwargs, {"Prefix": clave, "MaxKeys": 1000})
        self.assertEqual(operar.call_args_list[4].kwargs, {"Key": clave})

    def test_borrado_fisico_acepta_solo_version_null_actual_no_versionada(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=[
            {},
            {"Versions": [{"Key": clave, "VersionId": "null", "IsLatest": True}],
             "DeleteMarkers": [], "IsTruncated": False},
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
        ]) as operar:
            self.cliente.borrar_fisico_verificado(clave)
        self.assertEqual(operar.call_args_list[2].args[0], "delete_object")
        self.assertNotIn("VersionId", operar.call_args_list[2].kwargs)

    def test_borrado_fisico_versionado_o_historial_no_elimina_por_clave(self):
        clave = nueva_clave_final(uuid4())
        for config, versionado in (({"Status": "Enabled"}, True),
                                   ({"Status": "Suspended"}, True), ({}, False)):
            with self.subTest(config=config):
                respuestas = [config]
                if not versionado:
                    respuestas.append({"Versions": [{"Key": clave, "VersionId": "v1"}],
                                       "DeleteMarkers": [], "IsTruncated": False})
                with patch.object(self.cliente, "_operar", side_effect=respuestas) as operar:
                    with self.assertRaises(ErrorS3):
                        self.cliente.borrar_fisico_verificado(clave)
                self.assertFalse(any(call.args[0] == "delete_object" for call in operar.call_args_list))

    def test_borrado_fisico_sin_permiso_para_consultar_versionado_no_hace_delete(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=ErrorS3("acceso")) as operar:
            with self.assertRaises(ErrorS3):
                self.cliente.borrar_fisico_verificado(clave)
        operar.assert_called_once_with("get_bucket_versioning")

    def test_borrado_fisico_no_confunde_ausencia_no_demostrada_con_exito(self):
        clave = nueva_clave_final(uuid4())
        escenarios = (
            ([{}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              ErrorS3("acceso")], "fallo_delete"),
            ([{}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              {}, {"Versions": [{"Key": clave, "VersionId": "null", "IsLatest": True}],
                   "DeleteMarkers": [], "IsTruncated": False}], "sigue_presente"),
            ([{}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              {}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              ErrorS3("acceso")], "head_denegado"),
            ([{}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              {}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              ErrorS3("servicio")], "head_timeout"),
        )
        for respuestas, nombre in escenarios:
            with self.subTest(escenario=nombre), patch.object(
                    self.cliente, "_operar", side_effect=respuestas):
                with self.assertRaises(ErrorS3):
                    self.cliente.borrar_fisico_verificado(clave)

    def test_borrado_fisico_ausente_se_puede_recuperar_sin_crear_markers(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=[
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
        ]) as operar:
            self.cliente.borrar_fisico_verificado(clave)
        self.assertEqual(operar.call_args_list[2].args[0], "delete_object")
        self.assertEqual(operar.call_args_list[2].kwargs, {"Key": clave})

    def test_borrado_fisico_pagina_historial_acotada_y_ausencia_final(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=[
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": True,
             "NextKeyMarker": clave + "-otro", "NextVersionIdMarker": "v1"},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            ErrorS3("ausente"),
        ]) as operar:
            self.cliente.borrar_fisico_verificado(clave)
        self.assertEqual(operar.call_args_list[2].kwargs, {
            "Prefix": clave, "MaxKeys": 1000, "KeyMarker": clave + "-otro",
            "VersionIdMarker": "v1",
        })

    def test_borrado_fisico_listados_s3_inciertos_no_llegan_a_delete(self):
        clave = nueva_clave_final(uuid4())
        escenarios = (
            ([{}, ErrorS3("acceso")], "listado_inicial"),
            ([{}, {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
              {}, ErrorS3("servicio")], "listado_final"),
        )
        for respuestas, nombre in escenarios:
            with self.subTest(escenario=nombre), patch.object(
                    self.cliente, "_operar", side_effect=respuestas) as operar:
                with self.assertRaises(ErrorS3):
                    self.cliente.borrar_fisico_verificado(clave)
                if nombre == "listado_inicial":
                    self.assertFalse(any(c.args[0] == "delete_object" for c in operar.call_args_list))
                else:
                    self.assertIn("delete_object", [c.args[0] for c in operar.call_args_list])

    def test_borrado_fisico_head_presente_no_se_cierra(self):
        clave = nueva_clave_final(uuid4())
        with patch.object(self.cliente, "_operar", side_effect=[
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            {},
            {"Versions": [], "DeleteMarkers": [], "IsTruncated": False},
            {"ContentLength": 5},
        ]) as operar:
            with self.assertRaises(ErrorS3):
                self.cliente.borrar_fisico_verificado(clave)
        self.assertEqual(operar.call_args_list[-1].args[0], "head_object")

    def test_hash_real_y_cierre_stream(self):
        contenido = b"bytes reales del archivo"
        stream = StreamingBody(BytesIO(contenido), len(contenido))
        with patch.object(self.cliente, "_operar", return_value={"Body": stream}):
            resultado = self.cliente.verificar_contenido(self.temporal, maximo_bytes=len(contenido))
        self.assertEqual(resultado.sha256, hashlib.sha256(contenido).hexdigest())
        self.assertEqual(resultado.tamano_bytes, len(contenido))
        self.assertTrue(stream._raw_stream.closed)

    def test_exceso_de_contenido_no_se_acepta_y_cierra_stream(self):
        stream = StreamingBody(BytesIO(b"12345"), 5)
        with patch.object(self.cliente, "_operar", return_value={"Body": stream}):
            with self.assertRaises(ErrorS3) as exc:
                self.cliente.verificar_contenido(self.temporal, maximo_bytes=4)
        self.assertEqual(exc.exception.tipo, "contenido")
        self.assertTrue(stream._raw_stream.closed)

    def test_limites_reintentos_y_verificacion_tls(self):
        config = self.cliente._cliente.meta.config
        self.assertEqual(config.retries["total_max_attempts"], 3)
        self.assertEqual(config.connect_timeout, 5)
        self.assertEqual(config.read_timeout, 15)
        self.assertEqual(config.signature_version, "s3v4")
