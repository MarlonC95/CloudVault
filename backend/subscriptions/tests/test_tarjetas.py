"""§10.5 — Tarjetas de pago simulado: alta (máx. 2), actualización y baja."""

from datetime import date

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from common.testing import cliente_autenticado, espacio_de_trabajo
from subscriptions import services
from subscriptions.models import MetodoPago

TARJETAS = "/api/v1/mi-plan/tarjetas/"
VISA = "4242 4242 4242 4242"
MASTERCARD = "5555-5555-5555-4444"


def datos_tarjeta(**cambios):
    datos = {
        "titular": "Ana Prueba", "numero": VISA, "cvv": "123",
        "mes_expiracion": 12, "anio_expiracion": 2030, "tipo": "credito",
    }
    datos.update(cambios)
    return datos


class ValidacionTarjetaTests(SimpleTestCase):
    hoy = date(2026, 11, 12)

    def test_luhn_y_marca(self):
        self.assertTrue(services.luhn_valido("4242424242424242"))
        self.assertFalse(services.luhn_valido("4242424242424241"))
        self.assertEqual(services.marca_tarjeta("4242424242424242"), "visa")
        self.assertEqual(services.marca_tarjeta("5555555555554444"), "mastercard")
        self.assertEqual(services.marca_tarjeta("2223003122003222"), "mastercard")
        self.assertEqual(services.marca_tarjeta("378282246310005"), "amex")
        self.assertEqual(services.marca_tarjeta("6011111111111117"), "otra")

    def test_alta_valida_guarda_solo_datos_no_sensibles(self):
        limpio, errores = services.validar_tarjeta(datos_tarjeta(), self.hoy)
        self.assertEqual(errores, {})
        self.assertEqual(limpio, {
            "titular": "Ana Prueba", "tipo": "CREDITO", "marca": "visa",
            "ultimos4": "4242", "mes_expiracion": 12, "anio_expiracion": 2030,
        })

    def test_rechaza_numero_cvv_y_fecha_invalidos(self):
        _, errores = services.validar_tarjeta(
            datos_tarjeta(numero="4242424242424241", cvv="12", anio_expiracion=2026,
                          mes_expiracion=10, tipo="prepago", titular=" "),
            self.hoy,
        )
        self.assertEqual(
            set(errores), {"numero", "cvv", "anio_expiracion", "tipo", "titular"}
        )

    def test_amex_exige_cvv_de_4(self):
        _, errores = services.validar_tarjeta(
            datos_tarjeta(numero="378282246310005", cvv="123"), self.hoy
        )
        self.assertEqual(set(errores), {"cvv"})

    def test_mes_en_curso_sigue_vigente(self):
        _, errores = services.validar_tarjeta(
            datos_tarjeta(mes_expiracion=11, anio_expiracion=2026), self.hoy
        )
        self.assertEqual(errores, {})

    def test_edicion_parcial_solo_valida_lo_enviado(self):
        actual = MetodoPago(mes_expiracion=1, anio_expiracion=2030)
        limpio, errores = services.validar_tarjeta({"mes_expiracion": 5}, self.hoy, actual)
        self.assertEqual(errores, {})
        self.assertEqual(limpio, {"mes_expiracion": 5, "anio_expiracion": 2030})
        _, errores = services.validar_tarjeta({"numero": MASTERCARD}, self.hoy, actual)
        self.assertEqual(set(errores), {"cvv"})


class TarjetasApiTests(TestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def crear(self, **cambios):
        return self.client.post(TARJETAS, datos_tarjeta(**cambios), format="json")

    def test_alta_lista_y_primera_es_predeterminada(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        tarjeta = respuesta.data["data"]
        self.assertEqual(tarjeta["marca"], "visa")
        self.assertEqual(tarjeta["ultimos4"], "4242")
        self.assertEqual(tarjeta["tipo"], "credito")
        self.assertTrue(tarjeta["predeterminada"])
        self.assertNotIn("numero", tarjeta)
        self.assertNotIn("cvv", tarjeta)

        segunda = self.crear(numero=MASTERCARD, tipo="debito").data["data"]
        self.assertFalse(segunda["predeterminada"])
        listado = self.client.get(TARJETAS).data["data"]
        self.assertEqual([t["ultimos4"] for t in listado], ["4242", "4444"])

    def test_maximo_dos_tarjetas(self):
        self.crear()
        self.crear(numero=MASTERCARD)
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("tarjetas", respuesta.data["error"]["fields"])
        self.assertEqual(MetodoPago.objects.count(), 2)

    def test_alta_invalida_no_guarda(self):
        respuesta = self.crear(numero="1234")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(MetodoPago.objects.count(), 0)

    def test_actualizar_reemplaza_tarjeta_y_cambia_predeterminada(self):
        primera = self.crear().data["data"]
        segunda = self.crear(numero=MASTERCARD).data["data"]
        respuesta = self.client.patch(
            f"{TARJETAS}{segunda['id']}/",
            {"numero": VISA, "cvv": "999", "mes_expiracion": 3, "predeterminada": True},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        data = respuesta.data["data"]
        self.assertEqual((data["marca"], data["mes_expiracion"]), ("visa", 3))
        self.assertTrue(data["predeterminada"])
        self.assertFalse(MetodoPago.objects.get(id=primera["id"]).predeterminada)

    def test_eliminar_predeterminada_promueve_la_otra(self):
        primera = self.crear().data["data"]
        segunda = self.crear(numero=MASTERCARD).data["data"]
        respuesta = self.client.delete(f"{TARJETAS}{primera['id']}/")
        self.assertEqual(respuesta.status_code, 204)
        self.assertTrue(MetodoPago.objects.get(id=segunda["id"]).predeterminada)

    def test_tarjeta_de_otra_organizacion_es_404(self):
        otro_usuario, _ = espacio_de_trabajo()
        ajena = cliente_autenticado(otro_usuario).post(
            TARJETAS, datos_tarjeta(), format="json"
        ).data["data"]
        respuesta = self.client.patch(
            f"{TARJETAS}{ajena['id']}/", {"titular": "Intruso"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self.client.delete(f"{TARJETAS}{ajena['id']}/").status_code, 404)

    def test_solo_propietario(self):
        usuario_id, _ = espacio_de_trabajo(nivel_rol=2)
        cliente = cliente_autenticado(usuario_id)
        self.assertEqual(cliente.get(TARJETAS).status_code, 403)
        self.assertEqual(cliente.post(TARJETAS, datos_tarjeta(), format="json").status_code, 403)
        self.assertEqual(APIClient().get(TARJETAS).status_code, 401)
