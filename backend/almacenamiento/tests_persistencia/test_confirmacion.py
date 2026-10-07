"""SQL real desechable; negocio y bucket son fixtures explícitas, sin Railway."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import OperationalError, connection, connections, transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from auth_workspaces.models import LogAuditoria
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.confirmacion import ServicioConfirmacionCargas
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.integracion import ArchivoVerificado
from almacenamiento.models import EstadoPublicacion, EstadoSesion, IntentoPublicacion, SesionCarga
from almacenamiento.persistencia import IntegridadCarga, RepositorioCargas
from almacenamiento.s3 import ContenidoS3, ErrorS3, ObjetoS3, nueva_clave_final
from . import test_inicio


class BucketSintetico:
    def __init__(self):
        self.objetos = {}
        self.copias = 0
        self.consultas = 0
        self.despues_copia = None
        self.antes_copia = None
        self.cerrar = Mock()

    def consultar(self, clave):
        assert not connections["default"].in_atomic_block, "S3 dentro de transacción"
        self.consultas += 1
        if clave not in self.objetos:
            raise ErrorS3("ausente")
        contenido, mime = self.objetos[clave]
        return ObjetoS3(len(contenido), mime, '"' + hashlib.sha256(contenido).hexdigest() + '"')

    def publicar_una_vez(self, origen, destino, **kwargs):
        assert not connections["default"].in_atomic_block, "COPY bajo locks de cuota"
        self.copias += 1
        if self.antes_copia:
            self.antes_copia()
        assert destino not in self.objetos, "Sobrescritura de final"
        self.objetos[destino] = (self.objetos[origen][0], "application/octet-stream")
        if self.despues_copia:
            self.despues_copia()

    def verificar(self, *, clave, tamano_bytes):
        assert not connections["default"].in_atomic_block, "Hash bajo cuota"
        contenido = self.objetos[clave][0]
        if len(contenido) > tamano_bytes:
            raise ErrorS3("contenido")
        return ContenidoS3(len(contenido), hashlib.sha256(contenido).hexdigest())


class ConfirmacionPersistenteTests(SimpleTestCase):
    databases = {"default"}
    destino = test_inicio.InicioPersistenteTests.destino
    cuota = test_inicio.InicioPersistenteTests.cuota
    firmador = test_inicio.InicioPersistenteTests.firmador

    def setUp(self):
        test_inicio.InicioPersistenteTests.setUp(self)
        self.proveedor.registrar_archivo = Mock(side_effect=self.registrar)
        self.proveedor.autorizar_descarga = Mock(side_effect=self.leer_archivo)
        self.sesion = test_inicio.InicioPersistenteTests.reservar_anterior(self, tamano=5)
        self.bucket = BucketSintetico()
        self.bucket.objetos[self.sesion.clave_temporal] = (b"12345", "text/plain")
        self.fabrica_bucket = Mock(return_value=self.bucket)
        self.verificador = Mock(side_effect=self.bucket.verificar)

    def registrar(self, *, archivo):
        assert connections["default"].in_atomic_block
        with connections["default"].cursor() as cursor:
            cursor.execute("""INSERT INTO archivos
                (id,organizacion_id,carpeta_id,propietario_id,nombre_original,clave_s3,
                 tamano_bytes,tipo_mime,checksum_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", [
                    archivo.archivo_id, archivo.organizacion_id, archivo.carpeta_id,
                    archivo.solicitante_id, archivo.nombre, archivo.clave_final,
                    archivo.tamano_bytes, archivo.tipo_mime, archivo.checksum_sha256])
            # Autoridad de consumo sintética exclusiva de este servidor de pruebas.
            cursor.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=almacenamiento_usado_bytes+%s WHERE id=%s",
                           [archivo.tamano_bytes, archivo.organizacion_id])

    def leer_archivo(self, *, solicitante_id, archivo_id):
        with connections["default"].cursor() as cursor:
            cursor.execute("""SELECT id,organizacion_id,carpeta_id,nombre_original,clave_s3,
                tamano_bytes,tipo_mime,checksum_sha256 FROM archivos WHERE id=%s AND propietario_id=%s""",
                           [archivo_id, solicitante_id])
            fila = cursor.fetchone()
        if fila is None:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)
        return ArchivoVerificado(fila[0], solicitante_id, *fila[1:])

    def servicio(self, **kwargs):
        return ServicioConfirmacionCargas(
            servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=self.fabrica_bucket, verificador=self.verificador, **kwargs)

    def confirmar(self, servicio=None, **cambios):
        datos = dict(solicitante_id=self.actor, archivo_id=str(self.sesion.archivo_id), datos={})
        datos.update(cambios)
        return (servicio or self.servicio()).confirmar(**datos)

    def filas(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM archivos")
            return cursor.fetchone()[0]

    def assert_pendiente_sin_metadatos(self):
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.PENDING)
        self.assertEqual(self.filas(), 0)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)

    def test_confirmacion_durable_id_hash_mime_evento_y_incremento_unico(self):
        resultado = self.confirmar()
        self.assertEqual(resultado, {"data": {"id": str(self.sesion.archivo_id),
            "nombre": self.sesion.nombre, "es_nuevo": True, "en_papelera": False}})
        self.sesion.refresh_from_db()
        intento = IntentoPublicacion.objects.get(sesion=self.sesion)
        self.assertEqual(intento.estado, EstadoPublicacion.PUBLISHED)
        self.assertIsNone(intento.checksum_origen)
        self.assertEqual(self.sesion.estado, EstadoSesion.CONFIRMED)
        self.assertEqual(self.sesion.checksum_sha256, hashlib.sha256(b"12345").hexdigest())
        archivo = self.leer_archivo(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.assertEqual(archivo.checksum_sha256, self.sesion.checksum_sha256)
        self.assertEqual(archivo.tipo_mime, "application/octet-stream")
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)
        self.assertEqual(LogAuditoria.objects.get().accion, "CARGA_CONFIRMADA")
        self.assertEqual(self.bucket.copias, 1)
        # Limpieza reconstructible, no borrado del final ni temporal bajo firma vigente.
        self.assertIn(self.sesion.clave_temporal, self.bucket.objetos)
        self.assertFalse(connection.in_atomic_block)

    def test_repetir_en_otro_servicio_sin_s3_copia_evento_o_consumo_extra(self):
        primera = self.confirmar()
        consultas = self.bucket.consultas
        segunda = self.confirmar(self.servicio(), datos={"etag": '"otra-pista"'})
        self.assertEqual(primera, segunda)
        self.assertEqual(self.bucket.consultas, consultas)
        self.assertEqual(self.bucket.copias, 1)
        self.assertEqual(self.filas(), 1)
        self.assertEqual(LogAuditoria.objects.count(), 1)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_actor_ajeno_es_404_sin_bucket(self):
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar(solicitante_id=self.otro_actor)
        self.assertEqual(error.exception.codigo, CodigoError.NO_ENCONTRADO)
        self.fabrica_bucket.assert_not_called()

    def test_temporal_ausente_reintentable_sin_ledger(self):
        self.bucket.objetos.clear()
        with self.assertRaises(ErrorS3) as error:
            self.confirmar()
        self.assertEqual(error.exception.tipo, "ausente")
        self.assertFalse(IntentoPublicacion.objects.exists())
        self.assert_pendiente_sin_metadatos()

    def test_storage_403_no_equivale_a_objeto_ausente(self):
        self.bucket.consultar = Mock(side_effect=ErrorS3("acceso"))
        with self.assertRaises(ErrorS3) as error:
            self.confirmar()
        self.assertEqual(error.exception.codigo, CodigoError.SERVICE_UNAVAILABLE)
        self.assert_pendiente_sin_metadatos()

    def test_etag_pista_incorrecta_rechaza_sin_cancelar_o_copiar(self):
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar(datos={"etag": '"incorrecto"'})
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.bucket.copias, 0)
        self.assert_pendiente_sin_metadatos()

    def test_tamano_temporal_incorrecto_cancela_y_libera_una_vez(self):
        self.bucket.objetos[self.sesion.clave_temporal] = (b"123456", "text/plain")
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.CANCELED)
        self.assertFalse(IntentoPublicacion.objects.exists())
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assertEqual(LogAuditoria.objects.count(), 1)
        self.assertEqual(self.filas(), 0)
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.org):
            self.assertEqual(repo.bytes_pendientes(organizacion_id=self.org), 0)

    def test_origen_cambia_durante_copy_hash_del_final_recibido(self):
        self.bucket.antes_copia = lambda: self.bucket.objetos.update({self.sesion.clave_temporal: (b"abcde", "text/html")})
        self.confirmar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.checksum_sha256, hashlib.sha256(b"abcde").hexdigest())
        self.bucket.objetos[self.sesion.clave_temporal] = (b"nueva carga", "text/html")
        self.confirmar()
        self.assertEqual(self.bucket.objetos[nueva_clave_final(self.sesion.archivo_id)][0], b"abcde")

    def test_final_sobredimensionado_abandona_y_cancela_sin_borrarlo(self):
        self.bucket.antes_copia = lambda: self.bucket.objetos.update({self.sesion.clave_temporal: (b"123456", "text/plain")})
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.CANCELED)
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.ABANDONED)
        self.assertIn(nueva_clave_final(self.sesion.archivo_id), self.bucket.objetos)
        self.assertEqual(self.filas(), 0)

    def test_final_mime_no_seguro_no_publica(self):
        self.bucket.despues_copia = lambda: self.bucket.objetos.update({nueva_clave_final(self.sesion.archivo_id): (b"12345", "text/html")})
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()

    def test_caida_antes_copy_prepared_no_repite_desde_temporal(self):
        self.bucket.antes_copia = Mock(side_effect=ErrorS3())
        with self.assertRaises(ErrorS3):
            self.confirmar()
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.PREPARED)
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar(self.servicio())
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.bucket.copias, 1)
        self.assert_pendiente_sin_metadatos()

    def test_copy_ambiguo_ya_creado_recupera_sin_temporal_o_recopia(self):
        self.bucket.despues_copia = Mock(side_effect=ErrorS3())
        with self.assertRaises(ErrorS3):
            self.confirmar()
        del self.bucket.objetos[self.sesion.clave_temporal]
        self.confirmar(self.servicio())
        self.assertEqual(self.bucket.copias, 1)
        self.assertEqual(self.filas(), 1)

    def test_registro_sql_fallido_revierte_y_recupera_final_sin_copy(self):
        def fallo(*, archivo):
            self.registrar(archivo=archivo)
            raise OperationalError("synthetic-private-db-error")
        self.proveedor.registrar_archivo.side_effect = fallo
        with self.assertRaises(OperationalError):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.PREPARED)
        self.proveedor.registrar_archivo.side_effect = self.registrar
        self.confirmar(self.servicio())
        self.assertEqual(self.bucket.copias, 1)

    def test_auditoria_fallida_revierte_metadatos_consumo_y_sesion(self):
        with self.assertRaises(OperationalError):
            self.confirmar(self.servicio(auditoria=Mock(side_effect=OperationalError("synthetic-audit"))))
        self.assert_pendiente_sin_metadatos()
        self.assertEqual(LogAuditoria.objects.count(), 0)
        self.confirmar()
        self.assertEqual(self.bucket.copias, 1)

    def test_commit_final_fallido_no_exito_y_reintento_mismo_final(self):
        original = connection.commit
        commits = []
        def commit():
            commits.append(1)
            if len(commits) == 3:
                raise OperationalError("synthetic-final-commit")
            original()
        with patch.object(connection, "commit", side_effect=commit), self.assertRaises(OperationalError):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.confirmar()
        self.assertEqual(self.bucket.copias, 1)

    def test_contador_sin_actualizar_o_doble_incremento_revierte(self):
        def registrar_doble(*, archivo):
            self.registrar(archivo=archivo)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=almacenamiento_usado_bytes+%s WHERE id=%s",
                               [archivo.tamano_bytes, self.org])
        self.proveedor.registrar_archivo.side_effect = registrar_doble
        with self.assertRaises(IntegridadCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.PREPARED)

    def test_proveedor_omite_consumo_y_no_se_certifica_registro(self):
        def sin_consumo(*, archivo):
            self.registrar(archivo=archivo)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=80 WHERE id=%s", [self.org])
        self.proveedor.registrar_archivo.side_effect = sin_consumo
        with self.assertRaises(IntegridadCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()

    def test_metadatos_devuelven_otra_clave_o_hash_revierte(self):
        original = self.leer_archivo
        self.proveedor.autorizar_descarga.side_effect = lambda **kwargs: replace(
            original(**kwargs), checksum_sha256="0" * 64)
        with self.assertRaises(IntegridadCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()

    def test_archivo_vacio_hash_correcto_consumo_cero(self):
        SesionCarga.objects.filter(pk=self.sesion.pk).update(tamano_bytes=0)
        self.bucket.objetos[self.sesion.clave_temporal] = (b"", "text/plain")
        self.confirmar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.checksum_sha256, hashlib.sha256(b"").hexdigest())
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)

    def test_proveedor_incompleto_falla_503_sin_sql_o_bucket(self):
        del self.proveedor.registrar_archivo
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar()
        self.assertEqual(error.exception.status_code, 503)
        self.fabrica_bucket.assert_not_called()

    def test_final_corto_detectado_por_hash_cancela(self):
        self.verificador.side_effect = lambda **kwargs: ContenidoS3(4, hashlib.sha256(b"1234").hexdigest())
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.CANCELED)
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.ABANDONED)

    def test_cuota_incluye_reserva_propia_una_vez_y_downgrade_se_revalida(self):
        self.limite = 85
        self.confirmar()
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_downgrade_despues_copy_no_publica(self):
        self.bucket.despues_copia = lambda: setattr(self, "limite", 80)
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar()
        self.assertEqual(error.exception.codigo, CodigoError.CUOTA_EXCEDIDA)
        self.assert_pendiente_sin_metadatos()

    def test_revocacion_despues_verificar_y_en_reintento_confirmado(self):
        def verificar(**kwargs):
            contenido = self.bucket.verificar(**kwargs)
            self.proveedor.resolver_destino.side_effect = PermissionDenied()
            return contenido
        self.verificador.side_effect = verificar
        with self.assertRaises(PermissionDenied):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.proveedor.resolver_destino.side_effect = self.destino
        self.verificador.side_effect = self.bucket.verificar
        self.confirmar()
        self.proveedor.autorizar_descarga.side_effect = PermissionDenied()
        with self.assertRaises(PermissionDenied):
            self.confirmar()
        self.assertEqual(self.filas(), 1)
        self.assertEqual(self.bucket.copias, 1)

    def test_vence_durante_copy_no_publica_y_reintento_rechazado(self):
        def vencer():
            from datetime import timedelta
            SesionCarga.objects.filter(pk=self.sesion.pk).update(
                creado_en=timezone.now()-timedelta(minutes=5),
                expira_en=timezone.now()-timedelta(seconds=1))
        self.bucket.despues_copia = vencer
        with self.assertRaises(ErrorCarga) as error:
            self.confirmar()
        self.assertEqual(error.exception.status_code, 400)
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assertEqual(self.bucket.copias, 1)
        self.assert_pendiente_sin_metadatos()

    def test_final_preexistente_sin_ledger_nunca_se_sobrescribe(self):
        clave = nueva_clave_final(self.sesion.archivo_id)
        self.bucket.objetos[clave] = (b"otros", "application/octet-stream")
        with self.assertRaises(IntegridadCarga):
            self.confirmar()
        self.assertFalse(IntentoPublicacion.objects.exists())
        self.assertEqual(self.bucket.copias, 0)

    def test_worker_falla_sin_metadatos_y_recupera_sin_recopia(self):
        self.verificador.side_effect = ErrorS3()
        with self.assertRaises(ErrorS3):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.verificador.side_effect = self.bucket.verificar
        self.confirmar()
        self.assertEqual(self.bucket.copias, 1)

    def test_final_cambia_durante_verificacion_rechazo_sin_exito(self):
        def verificar(**kwargs):
            contenido = self.bucket.verificar(**kwargs)
            self.bucket.objetos[kwargs["clave"]] = (b"abcde", "application/octet-stream")
            return contenido
        self.verificador.side_effect = verificar
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()

    def test_reserva_cambia_durante_copy_no_confirma_metadatos_con_otro_tamano(self):
        self.bucket.despues_copia = lambda: SesionCarga.objects.filter(pk=self.sesion.pk).update(tamano_bytes=6)
        with self.assertRaises(IntegridadCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()

    def test_conexion_caida_libera_claim_y_reintento_solo_verifica(self):
        self.bucket.despues_copia = connection.close
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assert_pendiente_sin_metadatos()
        self.bucket.despues_copia = None
        self.confirmar()
        self.assertEqual(self.bucket.copias, 1)

    def test_transaccion_exterior_rechazada_antes_de_s3(self):
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.confirmar()
        self.fabrica_bucket.assert_not_called()

    def test_dos_confirmaciones_un_publicador_y_respuesta_recuperable(self):
        copiando, continuar = Event(), Event()
        def pausa():
            copiando.set()
            if not continuar.wait(timeout=5):
                raise RuntimeError("Timeout de fixture")
        self.bucket.despues_copia = pausa
        def confirmar():
            connections.close_all()
            try:
                return self.confirmar(self.servicio())
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            primera = pool.submit(confirmar)
            try:
                self.assertTrue(copiando.wait(timeout=5))
                with self.assertRaises(ErrorCarga) as error:
                    self.confirmar()
                self.assertEqual(error.exception.status_code, 503)
            finally:
                continuar.set()
            resultado = primera.result(timeout=5)
        self.assertEqual(self.confirmar(), resultado)
        self.assertEqual(self.bucket.copias, 1)
        self.assertEqual(self.filas(), 1)
        self.assertEqual(LogAuditoria.objects.count(), 1)

    def test_endpoint_200_con_sql_y_registro_sinteticos(self):
        cliente = APIClient()
        cliente.force_authenticate(SimpleNamespace(pk=self.actor, is_authenticated=True))
        with patch("almacenamiento.views.servicios_compartidos",
                   side_effect=lambda: ServiciosCompartidosValidados(self.proveedor)), \
             patch("almacenamiento.views.cliente_firmador", return_value=self.bucket), \
             patch("almacenamiento.views.verificador_publicacion", return_value=self.verificador):
            respuesta = cliente.post(f"/api/v1/archivos/{self.sesion.archivo_id}/confirmar-carga/", {}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["data"]["id"], str(self.sesion.archivo_id))
        self.assertEqual(self.filas(), 1)
