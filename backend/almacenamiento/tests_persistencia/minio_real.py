"""Ensayo opt-in contra MinIO NUEVO del controlador ejecutar_s3_local.

PostgreSQL y S3 reales. Proveedor de negocio y actor autorizado son fixtures.
No se descubre en la suite offline; exige marca del contenedor creado aquí.
"""

from datetime import timedelta
import hashlib
import os
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase
from django.utils import timezone

from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.configuracion_mantenimiento import PoliticaMantenimiento
from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.mantenimiento import ServicioMantenimiento
from almacenamiento.models import IntentoPublicacion, SesionCarga
from almacenamiento.probar_s3 import peticion
from almacenamiento.s3 import ClienteS3, ErrorS3, nueva_clave_final
from almacenamiento.verificacion import VerificadorSubproceso
from . import test_aceptacion


class MinioRealTests(SimpleTestCase):
    databases = {"default"}
    actor = test_aceptacion.AceptacionHTTPTests.actor
    iniciar = test_aceptacion.AceptacionHTTPTests.iniciar
    confirmar = test_aceptacion.AceptacionHTTPTests.confirmar
    estado_sql = test_aceptacion.AceptacionHTTPTests.estado_sql
    firmador = test_aceptacion.AceptacionHTTPTests.firmador

    def setUp(self):
        marca = os.environ.get("CLOUDVAULT_MINIO_PROPIO", "")
        config = ConfiguracionS3.desde_entorno(perfil="minio")
        if not marca or config.bucket != "fase8-" + marca or not config.endpoint.startswith("http://127.0.0.1:"):
            raise RuntimeError("MinIO ajeno al controlador de ensayo")
        test_aceptacion.AceptacionHTTPTests.setUp(self)
        self.config = config
        self.bucket = ClienteS3(config)
        self.addCleanup(self.bucket.cerrar)
        self.addCleanup(self.limpiar)
        self.claves = []
        self.copy_original = ClienteS3.publicar_una_vez
        self.copias = 0
        def copiar(cliente, *args, **kwargs):
            self.copias += 1
            return self.copy_original(cliente, *args, **kwargs)
        for parche in (
            patch("almacenamiento.views.cliente_firmador", side_effect=lambda: ClienteS3(config)),
            patch("almacenamiento.views.verificador_publicacion", return_value=VerificadorSubproceso(tiempo_maximo=10)),
            patch.object(ClienteS3, "publicar_una_vez", copiar),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def limpiar(self):
        for clave in self.claves:
            self.bucket.borrar_tecnico(clave)
            try:
                self.bucket.consultar(clave)
            except ErrorS3 as error:
                self.assertEqual(error.tipo, "ausente")
            else:
                self.fail("Objeto propio no eliminado")

    def cargar_real(self):
        inicio = self.iniciar()
        self.assertEqual(inicio.status_code, 201)
        sesion = SesionCarga.objects.get(archivo_id=inicio.data["data"]["archivo_id"])
        self.claves += [sesion.clave_temporal, nueva_clave_final(sesion.archivo_id)]
        estado, _, _ = peticion(inicio.data["data"]["url_subida"], metodo="PUT", cuerpo=b"12345",
                               headers=inicio.data["data"]["encabezados"])
        self.assertEqual(estado, 200)
        self.assertEqual(self.estado_sql(), (0, 5, 0))
        return sesion, inicio.data["data"]

    def test_flujo_http_put_copy_hash_descarga_y_limpieza_reales(self):
        sesion, inicio = self.cargar_real()
        confirmacion = self.confirmar(sesion)
        self.assertEqual(confirmacion.status_code, 200)
        self.assertEqual(self.confirmar(sesion).data, confirmacion.data)
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.actor(1)
        descarga = self.client.get(f"/api/v1/archivos/{sesion.archivo_id}/descarga/")
        self.assertEqual(descarga.status_code, 200)
        estado, contenido, headers = peticion(descarga.data["data"]["url_descarga"])
        self.assertEqual(estado, 200)
        self.assertEqual(contenido, b"12345")
        self.assertEqual(hashlib.sha256(contenido).hexdigest(), self.bucket.verificar_contenido(self.claves[1], maximo_bytes=5).sha256)
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        # Reutilizar la capability PUT no cambia el final ya publicado.
        estado, _, _ = peticion(inicio["url_subida"], metodo="PUT", cuerpo=b"abcde", headers=inicio["encabezados"])
        self.assertEqual(estado, 200)
        self.assertEqual(peticion(descarga.data["data"]["url_descarga"])[1], b"12345")
        SesionCarga.objects.filter(pk=sesion.pk).update(creado_en=timezone.now()-timedelta(minutes=20), expira_en=timezone.now()-timedelta(minutes=1))
        ServicioMantenimiento(servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=lambda: ClienteS3(self.config), politica=PoliticaMantenimiento(margen_segundos=1)).ejecutar()
        with self.assertRaises(ErrorS3) as error:
            self.bucket.consultar(self.claves[0])
        self.assertEqual(error.exception.tipo, "ausente")
        self.assertEqual(peticion(descarga.data["data"]["url_descarga"])[1], b"12345")
        self.assertEqual(self.copias, 1)
        self.assertEqual(self.estado_sql(), (5, 0, 1))

    def test_copy_real_sql_fallido_recupera_sin_recopiar(self):
        sesion, _ = self.cargar_real()
        registrar = self.proveedor.registrar_archivo
        def fallar(*, archivo):
            registrar(archivo=archivo)
            raise RuntimeError("Fallo sintético posterior al INSERT")
        self.proveedor.registrar_archivo = fallar
        self.assertEqual(self.confirmar(sesion).status_code, 500)
        self.assertEqual(self.estado_sql(), (0, 5, 0))
        self.assertEqual(IntentoPublicacion.objects.get(sesion=sesion).estado, "PREPARED")
        self.assertEqual(self.bucket.consultar(self.claves[1]).tamano_bytes, 5)
        self.proveedor.registrar_archivo = registrar
        self.assertEqual(self.confirmar(sesion).status_code, 200)
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.assertEqual(self.copias, 1)
