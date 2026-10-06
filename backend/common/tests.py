from django.test import SimpleTestCase
from rest_framework.decorators import api_view
from rest_framework.test import APIRequestFactory

from storage.services import get_used_bytes


@api_view(["GET"])
def _protegida(request):
    return None


class ErroresContratoTests(SimpleTestCase):
    def test_sin_token_responde_no_autenticado(self):
        request = APIRequestFactory().get("/x/")
        response = _protegida(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"error": {"code": "NO_AUTENTICADO"}})

    def test_stub_uso_almacenamiento(self):
        self.assertEqual(get_used_bytes(None), 0)
