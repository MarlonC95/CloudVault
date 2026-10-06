from django.test import SimpleTestCase
from rest_framework.decorators import api_view
from rest_framework.test import APIRequestFactory


@api_view(["GET"])
def _protegida(request):
    return None


class ErroresContratoTests(SimpleTestCase):
    def test_sin_token_responde_no_autenticado(self):
        request = APIRequestFactory().get("/x/")
        response = _protegida(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"error": {"code": "NO_AUTENTICADO"}})


class FormatoTamanoTests(SimpleTestCase):
    def test_formato_del_contrato_con_punto_decimal(self):
        from common.formatting import bytes_legibles

        casos = {
            0: "0 B",
            840 * 1024: "840 KB",
            4404019: "4.2 MB",
            128 * 1024**2: "128 MB",
            1503238554: "1.4 GB",
            1048575 * 1024: "1 GB",
        }
        for valor, esperado in casos.items():
            self.assertEqual(bytes_legibles(valor), esperado, valor)
        self.assertNotIn(",", bytes_legibles(4404019))
