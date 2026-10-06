from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.exceptions import (
    AuthenticationFailed, NotAuthenticated, NotFound, ParseError,
    PermissionDenied, Throttled, UnsupportedMediaType, ValidationError,
)
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework.authentication import BaseAuthentication

from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga, error_de_almacenamiento
from almacenamiento.serializers import ErrorSerializer


class ErroresCargaTests(SimpleTestCase):
    def test_errores_en_autenticacion_inicial_respetan_pdf_sin_exponer_detalles(self):
        secreto = "synthetic-auth-error-secret"
        for exc, status, code in (
            (NotAuthenticated(secreto), 401, "NO_AUTENTICADO"),
            (AuthenticationFailed(secreto), 401, "TOKEN_INVALIDO"),
            (PermissionDenied(secreto), 403, "SIN_PERMISO"),
        ):
            with self.subTest(code=code):
                class AutenticacionDePrueba(BaseAuthentication):
                    def authenticate(self, request):
                        raise exc

                    def authenticate_header(self, request):
                        return "Bearer"

                class VistaDePrueba(APIView):
                    authentication_classes = [AutenticacionDePrueba]
                    permission_classes = []
                    throttle_classes = []

                    def get_exception_handler(self):
                        return error_de_almacenamiento

                    def get(self, request):
                        raise AssertionError("No llegar a la operación sin autorización")

                response = VistaDePrueba.as_view()(APIRequestFactory().get("/prueba-local/"))
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.data, {"error": {"code": code, "fields": {}}})
                self.assertNotIn(secreto, str(response.data))
                if status == 401:
                    self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_handler_local_recibe_contexto_de_drf_en_vista_de_prueba(self):
        class VistaDePrueba(APIView):
            authentication_classes = []
            permission_classes = []
            throttle_classes = []

            def get_exception_handler(self):
                return error_de_almacenamiento

            def get(self, request):
                raise ParseError("detalle-no-publicable")

        response = VistaDePrueba.as_view()(APIRequestFactory().get("/prueba-local/"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": {
            "code": "VALIDATION_ERROR",
            "fields": {"non_field_errors": ["Se requiere un objeto JSON válido."]},
        }})

    def test_catalogo_pdf_y_status_sin_codigos_del_contrato_descartado(self):
        for exc, http, codigo in (
            (ValidationError({"nombre": ["Campo inválido."]}), 400, "VALIDATION_ERROR"),
            (ParseError(), 400, "VALIDATION_ERROR"),
            (UnsupportedMediaType("text/plain"), 400, "VALIDATION_ERROR"),
            (NotAuthenticated(), 401, "NO_AUTENTICADO"),
            (AuthenticationFailed(), 401, "TOKEN_INVALIDO"),
            (PermissionDenied(), 403, "SIN_PERMISO"),
            (NotFound(), 404, "NO_ENCONTRADO"),
            (ErrorCarga(CodigoError.CUOTA_EXCEDIDA), 409, "CUOTA_EXCEDIDA"),
            (Throttled(wait=2.1), 429, "RATE_LIMITED"),
            (OperationalError("credencial-ficticia"), 503, "SERVICE_UNAVAILABLE"),
        ):
            with self.subTest(codigo=codigo):
                response = error_de_almacenamiento(exc)
                self.assertEqual(response.status_code, http)
                self.assertEqual(response.data["error"]["code"], codigo)
                serializer = ErrorSerializer(data=response.data)
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_campos_de_validacion_conservan_lista_por_campo(self):
        response = error_de_almacenamiento(ValidationError({"tamano_bytes": ["Debe ser entero."]}))
        self.assertEqual(response.data, {"error": {
            "code": "VALIDATION_ERROR", "fields": {"tamano_bytes": ["Debe ser entero."]},
        }})

    def test_error_interno_y_db_no_revelan_detalles_en_body_o_log(self):
        secreto = "synthetic-secret-never-log-it"
        with self.assertLogs("almacenamiento.errores", level="ERROR") as logs:
            response = error_de_almacenamiento(RuntimeError(secreto))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"]["code"], "ERROR_INTERNO")
        self.assertNotIn(secreto, str(response.data) + "\n".join(logs.output))
        self.assertTrue(all(record.exc_info is None for record in logs.records))
        response = error_de_almacenamiento(OperationalError(secreto))
        self.assertNotIn(secreto, str(response.data))

    def test_headers_de_reautenticacion_y_reintento(self):
        for exc in (NotAuthenticated(), AuthenticationFailed()):
            self.assertEqual(error_de_almacenamiento(exc)["WWW-Authenticate"], "Bearer")
        self.assertEqual(error_de_almacenamiento(Throttled(wait=2.1))["Retry-After"], "3")

    def test_error_propio_no_permite_codigo_arbitrario(self):
        with self.assertRaises(ValueError):
            ErrorCarga("UPLOAD_EXPIRED")
