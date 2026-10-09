from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from common.testing import cliente_autenticado, espacio_de_trabajo
from storage.models import Archivo, Carpeta
from storage.servicios import crear_servicios


class ContratoStorageTests(APITestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo()
        self.client = cliente_autenticado(self.usuario_id)

    def url(self, nombre, *args):
        return f"{reverse(nombre, args=args)}?organizacion_id={self.organizacion_id}"

    def archivo(self, **datos):
        base = dict(organizacion_id=self.organizacion_id, propietario_id=self.usuario_id,
                    nombre="informe.pdf", clave_s3=f"cloudvault/dani/publicaciones/{uuid4()}",
                    tamano_bytes=1024, tipo_mime="application/pdf")
        base.update(datos)
        return Archivo.objects.create(**base)

    def test_formatos_y_ruta_calculada(self):
        padre = Carpeta.objects.create(organizacion_id=self.organizacion_id, nombre="Padre")
        hija = Carpeta.objects.create(organizacion_id=self.organizacion_id, padre=padre, nombre="Hija")
        archivo = self.archivo(carpeta=hija)
        respuesta = self.client.get(self.url("carpeta-detail", hija.pk))
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(set(respuesta.data["data"]), {"id", "nombre", "cantidad_archivos", "padre_id", "ruta_completa", "organizacion_id", "creado_en"})
        self.assertEqual(respuesta.data["data"]["ruta_completa"], "/Padre/Hija")
        self.assertEqual(respuesta.data["data"]["cantidad_archivos"], 1)
        self.assertEqual(self.client.get(self.url("carpeta-detail", padre.pk)).data["data"]["cantidad_archivos"], 1)
        respuesta = self.client.get(self.url("archivo-detail", archivo.pk))
        self.assertEqual(respuesta.data["data"]["tipo"], "pdf")
        self.assertEqual(respuesta.data["data"]["tamano_legible"], "1 KB")
        self.assertTrue(respuesta.data["data"]["cifrado"])

    def test_archivo_papelera_y_restauracion(self):
        archivo = self.archivo()
        respuesta = self.client.delete(self.url("archivo-detail", archivo.pk))
        self.assertEqual(respuesta.status_code, 200)
        archivo.refresh_from_db()
        self.assertTrue(archivo.en_papelera)
        self.assertIsNotNone(archivo.fecha_papelera)
        respuesta = self.client.get(self.url("papelera-list"))
        self.assertEqual(respuesta.data["data"]["count"], 1)
        self.assertEqual(respuesta.data["data"]["results"][0]["dias_restantes"], 30)
        respuesta = self.client.post(self.url("papelera-restaurar", archivo.pk))
        self.assertEqual(respuesta.status_code, 200)
        archivo.refresh_from_db()
        self.assertFalse(archivo.en_papelera)

    def test_borrado_definitivo_requiere_s3_exitoso(self):
        archivo = self.archivo(en_papelera=True, fecha_papelera=timezone.now())
        with patch("storage.views.ClienteS3") as cliente, patch("storage.views.ConfiguracionS3.desde_entorno"):
            cliente.return_value.borrar_tecnico.side_effect = ValueError("S3")
            self.assertEqual(self.client.delete(self.url("papelera-detail", archivo.pk)).status_code, 503)
            self.assertTrue(Archivo.objects.filter(pk=archivo.pk).exists())
            cliente.return_value.borrar_tecnico.side_effect = None
            self.assertEqual(self.client.delete(self.url("papelera-detail", archivo.pk)).status_code, 204)
            self.assertFalse(Archivo.objects.filter(pk=archivo.pk).exists())

    def test_resumen_usa_cuota_y_contadores(self):
        self.archivo()
        Carpeta.objects.create(organizacion_id=self.organizacion_id, nombre="Docs")
        respuesta = self.client.get(self.url("unidad-resumen"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["data"]["usado_bytes"], 1024)
        self.assertEqual(respuesta.data["data"]["cantidad_archivos"], 1)
        self.assertEqual(respuesta.data["data"]["cantidad_carpetas"], 1)

    def test_proveedor_real(self):
        proveedor = crear_servicios()
        destino = proveedor.resolver_destino(solicitante_id=self.usuario_id, carpeta_id=None)
        self.assertEqual(destino.organizacion_id, self.organizacion_id)
        self.assertGreater(proveedor.leer_cuota(organizacion_id=self.organizacion_id).limite_bytes, 0)
        with proveedor.bloquear_cuota(organizacion_id=self.organizacion_id):
            from almacenamiento.integracion import ArchivoVerificado
            id_archivo = uuid4()
            proveedor.registrar_archivo(archivo=ArchivoVerificado(
                id_archivo, self.usuario_id, self.organizacion_id, None,
                "nuevo.pdf", f"cloudvault/dani/publicaciones/{id_archivo}", 10,
                "application/pdf", None,
            ))
        autorizado = proveedor.autorizar_descarga(solicitante_id=self.usuario_id, archivo_id=id_archivo)
        self.assertEqual(autorizado.nombre, "nuevo.pdf")
        inspeccion = proveedor.inspeccionar_objeto_tecnico(
            sesion_id=uuid4(), organizacion_id=self.organizacion_id,
            clave=autorizado.clave_final,
        )
        self.assertTrue(inspeccion.referenciado)
        self.assertFalse(inspeccion.copia_concluida)
