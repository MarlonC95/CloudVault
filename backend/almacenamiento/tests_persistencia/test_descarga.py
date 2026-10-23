"""Descarga con SQL desechable, firmas offline y proveedor de negocio sintético."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Barrier, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from django.db import OperationalError, connection, connections, transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.test import APIClient

from auth_workspaces.models import LogAuditoria
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.contrato import CodigoError
from almacenamiento.descarga import ACCION_DESCARGA, ServicioDescargas
from almacenamiento.errores import ErrorCarga
from almacenamiento.models import EstadoPublicacion, EstadoSesion, IntentoPublicacion, SesionCarga
from almacenamiento.persistencia import IntegridadCarga
from almacenamiento.s3 import ClienteS3, ErrorS3, FirmaS3
from . import test_confirmacion


class DescargaPersistenteTests(SimpleTestCase):
    databases = {"default"}
    destino = test_confirmacion.ConfirmacionPersistenteTests.destino
    cuota = test_confirmacion.ConfirmacionPersistenteTests.cuota
    firmador = test_confirmacion.ConfirmacionPersistenteTests.firmador
    registrar = test_confirmacion.ConfirmacionPersistenteTests.registrar
    leer_archivo = test_confirmacion.ConfirmacionPersistenteTests.leer_archivo

    def setUp(self):
        test_confirmacion.ConfirmacionPersistenteTests.setUp(self)
        servicio = test_confirmacion.ConfirmacionPersistenteTests.servicio(self)
        test_confirmacion.ConfirmacionPersistenteTests.confirmar(self, servicio)
        self.archivo = self.leer_archivo(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.clientes_descarga = []
        self.fabrica_descarga = Mock(side_effect=self.cliente_descarga)
        self.config = ConfiguracionS3("railway", "https://s3.example.test", "auto",
                                    "bucket-sintetico", "synthetic-access", "synthetic-secret")

    def cliente_descarga(self):
        cliente = ClienteS3(self.config)
        cliente.consultar = Mock(side_effect=self.bucket.consultar)
        cliente.firmar_descarga = Mock(wraps=cliente.firmar_descarga)
        self.clientes_descarga.append(cliente)
        return cliente

    def servicio(self, **kwargs):
        return ServicioDescargas(
            servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=self.fabrica_descarga, **kwargs)

    def descargar(self, servicio=None, actor=None):
        return (servicio or self.servicio()).descargar(
            solicitante_id=actor or self.actor, archivo_id=str(self.sesion.archivo_id))

    def eventos(self):
        return LogAuditoria.objects.filter(accion=ACCION_DESCARGA)

    def test_url_correcta_nombre_utc_auditoria_sin_firma_y_sin_uso_extra(self):
        resultado = self.descargar()["data"]
        self.assertEqual(resultado["nombre"], self.archivo.nombre)
        self.assertTrue(resultado["expira_en"].endswith("Z"))
        self.assertEqual(urlsplit(resultado["url_descarga"]).path, "/"+self.archivo.clave_final)
        self.assertEqual(self.eventos().count(), 1)
        self.assertEqual(self.eventos().get().detalles, {"archivo_id": str(self.archivo.archivo_id)})
        self.assertNotIn(resultado["url_descarga"], str(self.eventos().get().detalles))
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)
        self.assertFalse(connection.in_atomic_block)

    def test_caller_con_permiso_no_tiene_que_ser_solicitante_original(self):
        self.proveedor.autorizar_descarga.side_effect = None
        self.proveedor.autorizar_descarga.return_value = replace(self.archivo, solicitante_id=self.otro_actor)
        self.descargar(actor=self.otro_actor)
        self.assertEqual(self.eventos().get().usuario_id, self.otro_actor)

    def test_actor_ajeno_y_papelera_denegados_por_proveedor_sin_sdk(self):
        for codigo in (CodigoError.SIN_PERMISO, CodigoError.NO_ENCONTRADO):
            self.proveedor.autorizar_descarga.side_effect = ErrorCarga(codigo)
            with self.assertRaises(ErrorCarga):
                self.descargar()
        self.fabrica_descarga.assert_not_called()
        self.assertEqual(self.eventos().count(), 0)

    def test_estado_no_confirmado_y_ledger_no_publicado_no_firman(self):
        for estado in (EstadoSesion.PENDING, EstadoSesion.CANCELED, EstadoSesion.EXPIRED):
            SesionCarga.objects.filter(pk=self.sesion.pk).update(estado=estado)
            with self.assertRaises(ErrorCarga):
                self.descargar()
        SesionCarga.objects.filter(pk=self.sesion.pk).update(estado=EstadoSesion.CONFIRMED)
        IntentoPublicacion.objects.filter(sesion=self.sesion).update(estado=EstadoPublicacion.ABANDONED)
        with self.assertRaises(IntegridadCarga):
            self.descargar()
        self.fabrica_descarga.assert_not_called()

    def test_temporal_otra_org_o_hash_incoherente_no_firman(self):
        for cambios in ({"clave_final": self.sesion.clave_temporal},
                         {"organizacion_id": self.otra_org}, {"checksum_sha256": "0" * 64}):
            self.proveedor.autorizar_descarga.side_effect = None
            self.proveedor.autorizar_descarga.return_value = replace(self.archivo, **cambios)
            with self.assertRaises(IntegridadCarga):
                self.descargar()
        self.fabrica_descarga.assert_not_called()

    def test_objeto_perdido_registra_inconsistencia_sin_firmar(self):
        del self.bucket.objetos[self.archivo.clave_final]
        with self.assertLogs("almacenamiento.descarga", level="WARNING") as logs, self.assertRaises(ErrorS3) as error:
            self.descargar()
        self.assertEqual(error.exception.codigo, CodigoError.NO_ENCONTRADO)
        self.assertIn(str(self.archivo.archivo_id), str(logs.output))
        self.assertNotIn(self.archivo.clave_final, str(logs.output))
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()
        self.assertEqual(self.eventos().count(), 0)

    def test_storage_403_timeout_no_equivalen_a_ausencia(self):
        for tipo in ("acceso", "servicio"):
            self.bucket.consultar = Mock(side_effect=ErrorS3(tipo))
            with self.assertRaises(ErrorS3) as error:
                self.descargar()
            self.assertEqual(error.exception.status_code, 503)
            self.clientes_descarga[-1].firmar_descarga.assert_not_called()

    def test_head_distinto_de_publicacion_no_firma(self):
        self.bucket.objetos[self.archivo.clave_final] = (b"abcde", "text/html")
        with self.assertLogs("almacenamiento.descarga", level="WARNING"), self.assertRaises(ErrorCarga):
            self.descargar()
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()

    def test_revocacion_tras_head_reautorizada_sin_nueva_url(self):
        self.proveedor.autorizar_descarga.side_effect = [self.archivo, PermissionDenied()]
        with self.assertRaises(PermissionDenied):
            self.descargar()
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()
        self.assertEqual(self.eventos().count(), 0)

    def test_rename_durante_head_rechazado_y_rename_estable_unicode_adjunto(self):
        self.proveedor.autorizar_descarga.side_effect = [self.archivo, replace(self.archivo, nombre="otro.txt")]
        with self.assertRaises(ErrorCarga):
            self.descargar()
        self.proveedor.autorizar_descarga.side_effect = None
        self.proveedor.autorizar_descarga.return_value = replace(self.archivo, nombre="informe español ✅.html", tipo_mime="text/html")
        respuesta = self.descargar()["data"]
        self.assertEqual(respuesta["nombre"], "informe español ✅.html")
        query = parse_qs(urlsplit(respuesta["url_descarga"]).query)
        self.assertEqual(query["response-content-type"], ["application/octet-stream"])
        self.assertTrue(query["response-content-disposition"][0].startswith("attachment;"))

    def test_firma_o_auditoria_fallida_no_cuenta_emision(self):
        cliente = self.cliente_descarga()
        cliente.firmar_descarga.side_effect = ErrorS3()
        self.fabrica_descarga.side_effect = None
        self.fabrica_descarga.return_value = cliente
        with self.assertRaises(ErrorS3):
            self.descargar()
        self.assertEqual(self.eventos().count(), 0)
        self.fabrica_descarga.side_effect = self.cliente_descarga
        with self.assertRaises(OperationalError):
            self.descargar(self.servicio(auditoria=Mock(side_effect=OperationalError("synthetic-private-audit"))))
        self.assertEqual(self.eventos().count(), 0)

    def test_commit_fallido_y_firma_incompatible_no_responden_exito(self):
        with patch.object(connection, "commit", side_effect=OperationalError("synthetic-commit")), self.assertRaises(OperationalError):
            self.descargar()
        self.assertEqual(self.eventos().count(), 0)
        cliente = self.cliente_descarga()
        cliente.firmar_descarga.return_value = FirmaS3("https://example.test/synthetic", "PUT", {}, timezone.now()+timedelta(seconds=500))
        self.fabrica_descarga.side_effect = None
        self.fabrica_descarga.return_value = cliente
        with self.assertRaises(IntegridadCarga):
            self.descargar()
        self.assertEqual(self.eventos().count(), 0)

    def test_limite_durable_otro_servicio_y_ventana_vencida(self):
        self.descargar(self.servicio(limite=1))
        with self.assertRaises(Throttled):
            self.descargar(self.servicio(limite=1))
        self.assertEqual(self.eventos().count(), 1)
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()
        self.eventos().update(fecha_evento=timezone.now()-timedelta(minutes=2))
        self.descargar(self.servicio(limite=1))
        self.assertEqual(self.eventos().count(), 2)

    def test_purga_eventos_antiguos_conserva_limite_activo(self):
        # Solo fixture privado; no instala un limpiador en la base compartida.
        self.descargar(self.servicio(limite=1))
        vigente = self.eventos().get()
        antiguo = LogAuditoria.objects.create(
            usuario_id=self.actor, organizacion_id=self.org, accion=ACCION_DESCARGA,
            fecha_evento=timezone.now()-timedelta(minutes=10),
            detalles={"archivo_id": str(self.archivo.archivo_id)})
        with self.assertRaises(Throttled):
            self.descargar(self.servicio(limite=1))
        corte = timezone.now()-timedelta(seconds=300)
        borrados, _ = self.eventos().filter(fecha_evento__lt=corte).delete()
        self.assertEqual(borrados, 1)
        self.assertFalse(LogAuditoria.objects.filter(pk=antiguo.pk).exists())
        self.assertEqual(self.eventos().get().pk, vigente.pk)
        with self.assertRaises(Throttled) as error:
            self.descargar(self.servicio(limite=1))
        self.assertGreater(error.exception.wait, 0)
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()
        self.assertEqual(self.eventos().count(), 1)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_purga_estricta_respeta_borde_de_ventana_mayor_a_300(self):
        ventana = 600
        self.descargar(self.servicio(limite=1, ventana_segundos=ventana))
        vigente = self.eventos().get()
        ahora = timezone.now()
        corte = ahora-timedelta(seconds=ventana)
        # El limitador usa >=: el evento exactamente en el corte sigue activo.
        self.eventos().filter(pk=vigente.pk).update(fecha_evento=corte)
        antiguo = LogAuditoria.objects.create(
            usuario_id=self.actor, organizacion_id=self.org, accion=ACCION_DESCARGA,
            fecha_evento=corte-timedelta(microseconds=1),
            detalles={"archivo_id": str(self.archivo.archivo_id)})
        with patch("almacenamiento.descarga.timezone.now", return_value=ahora):
            with self.assertRaises(Throttled):
                self.descargar(self.servicio(limite=1, ventana_segundos=ventana))
            borrados, _ = self.eventos().filter(fecha_evento__lt=corte).delete()
            self.assertEqual(borrados, 1)
            self.assertFalse(LogAuditoria.objects.filter(pk=antiguo.pk).exists())
            self.assertEqual(self.eventos().get().pk, vigente.pk)
            with self.assertRaises(Throttled):
                self.descargar(self.servicio(limite=1, ventana_segundos=ventana))
        self.clientes_descarga[-1].firmar_descarga.assert_not_called()
        self.assertEqual(self.eventos().count(), 1)

    def test_dos_conexiones_comparten_limite_una_firma_y_un_429(self):
        barrera = Barrier(2)
        def descargar():
            connections.close_all()
            try:
                barrera.wait(timeout=5)
                self.descargar(self.servicio(limite=1))
                return 200
            except Throttled:
                return 429
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = [f.result(timeout=5) for f in (pool.submit(descargar), pool.submit(descargar))]
        self.assertEqual(sorted(resultados), [200, 429])
        self.assertEqual(self.eventos().count(), 1)

    def test_transaccion_exterior_rechazada_antes_de_sdk(self):
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.descargar()
        self.fabrica_descarga.assert_not_called()

    def test_endpoint_http_200_429_y_retry_after(self):
        cliente = APIClient()
        cliente.force_authenticate(SimpleNamespace(pk=self.actor, is_authenticated=True))
        with patch("almacenamiento.views.servicios_compartidos",
                   side_effect=lambda: ServiciosCompartidosValidados(self.proveedor)), \
             patch("almacenamiento.views.cliente_firmador", side_effect=self.cliente_descarga), \
             patch("almacenamiento.views.entero_configurado",
                   side_effect=lambda nombre, defecto: 1 if nombre == "ALMACENAMIENTO_DESCARGAS_POR_VENTANA" else 60):
            ruta = f"/api/v1/archivos/{self.sesion.archivo_id}/descarga/"
            respuesta = cliente.get(ruta)
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            segunda = cliente.get(ruta)
            self.assertEqual(segunda.status_code, 429)
            self.assertEqual(segunda.data["error"]["code"], "RATE_LIMITED")
            self.assertGreaterEqual(int(segunda["Retry-After"]), 1)

    def test_get_real_local_bytes_del_final_anonimo_y_vencido_denegados(self):
        # Fixture HTTP local: allowlist de la URL firmada y reloj controlado.
        # No es una validación criptográfica del servidor Railway/S3.
        estado = {"autorizado": None, "vencido": False}
        contenido = self.bucket.objetos[self.archivo.clave_final][0]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                if estado["vencido"] or handler.path != estado["autorizado"]:
                    handler.send_response(403)
                    handler.end_headers()
                    return
                query = parse_qs(urlsplit(handler.path).query)
                handler.send_response(200)
                handler.send_header("Content-Type", "application/octet-stream")
                handler.send_header("Content-Disposition", query["response-content-disposition"][0])
                handler.send_header("Content-Length", str(len(contenido)))
                handler.end_headers()
                handler.wfile.write(contenido)
            def log_message(handler, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}"
            self.config = ConfiguracionS3("minio", endpoint, "us-east-1", "bucket-test",
                                        "synthetic-access", "synthetic-secret", estilo="path")
            salida = self.descargar()["data"]
            url = salida["url_descarga"]
            parsed = urlsplit(url)
            estado["autorizado"] = parsed.path+"?"+parsed.query
            with urlopen(url, timeout=3) as respuesta:
                recibido = respuesta.read()
                self.assertEqual(recibido, contenido)
                self.assertEqual(hashlib.sha256(recibido).hexdigest(), self.archivo.checksum_sha256)
                self.assertTrue(respuesta.headers["Content-Disposition"].startswith("attachment;"))
            with self.assertRaises(HTTPError) as anonimo:
                urlopen(endpoint+parsed.path, timeout=3)
            self.assertEqual(anonimo.exception.code, 403)
            estado["vencido"] = True
            with self.assertRaises(HTTPError) as vencido:
                urlopen(url, timeout=3)
            self.assertEqual(vencido.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
