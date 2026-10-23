from copy import deepcopy
from uuid import UUID

from django.test import SimpleTestCase

from almacenamiento.contrato import PoliticaCarga, TAMANO_SQL_MAXIMO
from almacenamiento.serializers import (
    ArchivoIdSerializer,
    BytesEnteros,
    ConfirmarCargaInputSerializer,
    ConfirmarCargaSuccessSerializer,
    DescargaSuccessSerializer,
    IniciarCargaInputSerializer,
    IniciarCargaSuccessSerializer,
)


CARPETA_ID = "22222222-2222-4222-8222-222222222222"
ARCHIVO_ID = "33333333-3333-4333-8333-333333333333"
INICIO = {
    "nombre": "demostración.pdf", "tamano_bytes": 1024,
    "tipo_mime": "application/pdf", "carpeta_id": CARPETA_ID,
}
RESPUESTA_INICIO = {"data": {
    "archivo_id": ARCHIVO_ID,
    "url_subida": "https://bucket.example.invalid/temporal?firma=ficticia",
    "metodo": "PUT", "encabezados": {"Content-Type": "application/pdf"},
    "expira_en": "2026-10-06T02:15:00Z",
}}
RESPUESTA_CONFIRMACION = {"data": {
    "id": ARCHIVO_ID, "nombre": INICIO["nombre"],
    "es_nuevo": True, "en_papelera": False,
}}
RESPUESTA_DESCARGA = {"data": {
    "url_descarga": "https://bucket.example.invalid/final?firma=ficticia",
    "nombre": INICIO["nombre"], "expira_en": "2026-10-06T02:05:00Z",
}}


class EntradaCargaTests(SimpleTestCase):
    def test_carga_valida_uuid_real_y_nombre_unicode(self):
        serializer = IniciarCargaInputSerializer(data=INICIO)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["carpeta_id"], UUID(CARPETA_ID))
        self.assertEqual(serializer.data, INICIO)

    def test_raiz_admite_null_u_omision_sin_inventar_organizacion(self):
        for value in (None, "omitida"):
            data = dict(INICIO)
            if value is None:
                data["carpeta_id"] = None
            else:
                data.pop("carpeta_id")
            serializer = IniciarCargaInputSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertIsNone(serializer.validated_data["carpeta_id"])
            self.assertNotIn("organizacion_id", serializer.validated_data)

    def test_cero_y_limite_bigint_admitidos_por_campo_estructural(self):
        campo = BytesEnteros(min_value=0, max_value=TAMANO_SQL_MAXIMO)
        for value in (0, TAMANO_SQL_MAXIMO):
            self.assertEqual(campo.run_validation(value), value)

    def test_limite_operativo_inicial_y_configurable_se_aplican_al_inicio(self):
        for politica in (PoliticaCarga(), PoliticaCarga(maximo_archivo_bytes=1024)):
            for value, valido in ((0, True), (politica.maximo_archivo_bytes, True),
                                  (politica.maximo_archivo_bytes + 1, False)):
                serializer = IniciarCargaInputSerializer(
                    data={**INICIO, "tamano_bytes": value}, context={"politica": politica}
                )
                self.assertEqual(serializer.is_valid(), valido)
                if not valido:
                    self.assertIn("tamano_bytes", serializer.errors)

    def test_bytes_no_coercion_de_booleanos_strings_o_fracciones(self):
        for value in (True, False, "1024", 1024.0, 1.5, -1, None, TAMANO_SQL_MAXIMO + 1):
            with self.subTest(value=value):
                serializer = IniciarCargaInputSerializer(data={**INICIO, "tamano_bytes": value})
                self.assertFalse(serializer.is_valid())
                self.assertIn("tamano_bytes", serializer.errors)

    def test_nombre_sin_rutas_o_inyeccion_y_limite_sql(self):
        invalidos = ("", "  ", ".", " .. ", "../a.pdf", "a\\b.pdf", "a\r\nb.pdf",
                     "a\x00b.pdf", "a" * 256, 42, None)
        for value in invalidos:
            with self.subTest(value=repr(value)):
                serializer = IniciarCargaInputSerializer(data={**INICIO, "nombre": value})
                self.assertFalse(serializer.is_valid())
                self.assertIn("nombre", serializer.errors)
        serializer = IniciarCargaInputSerializer(data={**INICIO, "nombre": "a" * 255})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_mime_valido_no_implica_lista_comercial_de_extensiones(self):
        for mime in ("application/pdf", "image/svg+xml", "text/html", "application/octet-stream"):
            serializer = IniciarCargaInputSerializer(data={**INICIO, "tipo_mime": mime})
            self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_mime_invalido_o_fuera_de_longitud(self):
        for value in ("pdf", "text/", "/plain", "text/plain\r\nX: y", "text/plain\n", "a/" + "b" * 99, 1, None):
            serializer = IniciarCargaInputSerializer(data={**INICIO, "tipo_mime": value})
            self.assertFalse(serializer.is_valid())
            self.assertIn("tipo_mime", serializer.errors)

    def test_uuid_no_admite_ids_del_ejemplo_o_tipo_incorrecto(self):
        for value in ("documentos", "subido-1700000000001", 1, True, "2" * 32):
            serializer = IniciarCargaInputSerializer(data={**INICIO, "carpeta_id": value})
            self.assertFalse(serializer.is_valid())
            self.assertIn("carpeta_id", serializer.errors)

    def test_campos_ajenos_y_requisitos_del_contrato_descartado_se_rechazan(self):
        for campo in ("organizacion_id", "plan_id", "propietario_cuota_id", "clave_s3",
                      "bucket", "checksum_sha256", "upload_id", "usado_bytes"):
            serializer = IniciarCargaInputSerializer(data={**INICIO, campo: "no-confiable"})
            self.assertFalse(serializer.is_valid())
            self.assertIn(campo, serializer.errors)

    def test_body_y_campos_obligatorios(self):
        for data in ([], None, "texto", 1):
            serializer = IniciarCargaInputSerializer(data=data)
            self.assertFalse(serializer.is_valid())
        for campo in ("nombre", "tamano_bytes", "tipo_mime"):
            data = dict(INICIO)
            data.pop(campo)
            serializer = IniciarCargaInputSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(campo, serializer.errors)


class ConfirmacionContratoTests(SimpleTestCase):
    def test_etag_opcional_se_conserva_sin_confundirlo_con_checksum(self):
        for body in ({}, {"etag": '"9c3b8f-multipart-2"'}):
            serializer = ConfirmarCargaInputSerializer(data=body)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.data, body)

    def test_etag_rechaza_null_controles_y_campos_ajenos(self):
        for body in ({"etag": None}, {"etag": ""}, {"etag": 123}, {"etag": "x\n"},
                     {"etag": "x" * 256}, {"upload_id": ARCHIVO_ID}, {"checksum_sha256": "a" * 64}):
            serializer = ConfirmarCargaInputSerializer(data=body)
            self.assertFalse(serializer.is_valid())

    def test_id_de_confirmacion_y_descarga_debe_ser_uuid(self):
        for value, valido in ((ARCHIVO_ID, True), ("subido-1", False), (True, False)):
            serializer = ArchivoIdSerializer(data={"id": value})
            self.assertEqual(serializer.is_valid(), valido)


class RespuestasContratoTests(SimpleTestCase):
    def test_arboles_y_campos_exactos_del_pdf(self):
        for cls, body in (
            (IniciarCargaSuccessSerializer, RESPUESTA_INICIO),
            (ConfirmarCargaSuccessSerializer, RESPUESTA_CONFIRMACION),
            (DescargaSuccessSerializer, RESPUESTA_DESCARGA),
        ):
            serializer = cls(data=body)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.data, body)

    def test_envoltorio_data_obligatorio_y_sin_campos_privados(self):
        for cls, body in ((IniciarCargaSuccessSerializer, RESPUESTA_INICIO),
                          (ConfirmarCargaSuccessSerializer, RESPUESTA_CONFIRMACION),
                          (DescargaSuccessSerializer, RESPUESTA_DESCARGA)):
            self.assertFalse(cls(data=body["data"]).is_valid())
            privado = deepcopy(body)
            privado["data"]["secret_access_key"] = "ficticia"
            self.assertFalse(cls(data=privado).is_valid())

    def test_subida_exige_put_content_type_y_fecha_valida(self):
        for campo, value in (("metodo", "POST"), ("expira_en", "no-fecha"),
                             ("encabezados", {"Authorization": "Bearer ficticio"}),
                             ("encabezados", {"Content-Type": "pdf"})):
            body = deepcopy(RESPUESTA_INICIO)
            body["data"][campo] = value
            self.assertFalse(IniciarCargaSuccessSerializer(data=body).is_valid())

    def test_fechas_de_respuesta_se_normalizan_a_utc(self):
        body = deepcopy(RESPUESTA_DESCARGA)
        body["data"]["expira_en"] = "2026-10-05T20:05:00-06:00"
        serializer = DescargaSuccessSerializer(data=body)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.data["data"]["expira_en"], "2026-10-06T02:05:00Z")

    def test_flags_no_aceptan_strings_o_enteros(self):
        for campo in ("es_nuevo", "en_papelera"):
            for value in (1, 0, "true", "false", None):
                body = deepcopy(RESPUESTA_CONFIRMACION)
                body["data"][campo] = value
                self.assertFalse(ConfirmarCargaSuccessSerializer(data=body).is_valid())
