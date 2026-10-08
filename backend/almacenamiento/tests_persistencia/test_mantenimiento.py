"""PostgreSQL y concurrencia reales; bucket/negocio sintéticos explícitos."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import json
import os
import subprocess
import sys
from threading import Event
import time
from unittest.mock import Mock
from uuid import uuid4

from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.test import SimpleTestCase
from django.utils import timezone

from auth_workspaces.models import LogAuditoria
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.configuracion_mantenimiento import PoliticaMantenimiento
from almacenamiento.confirmacion import ServicioConfirmacionCargas
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.integracion import InspeccionObjetoTecnico
from almacenamiento.mantenimiento import ServicioMantenimiento, auditar_mantenimiento
from almacenamiento.models import (
    EstadoMantenimiento, EstadoPublicacion, EstadoSesion, IntentoPublicacion,
    SesionCarga, TrabajoMantenimiento,
)
from almacenamiento.persistencia import EstadoIncompatible, IntegridadCarga, RepositorioCargas
from almacenamiento.s3 import ErrorS3, nueva_clave_final
from .test_confirmacion import BucketSintetico, ConfirmacionPersistenteTests


class WorkerInterrumpido(BaseException):
    pass


class BucketMantenimiento(BucketSintetico):
    def __init__(self):
        super().__init__()
        self.borrados = []
        self.antes_borrar = None
        self.despues_borrar = None

    def borrar_tecnico(self, clave):
        assert not connections["default"].in_atomic_block, "DELETE bajo transacción SQL"
        self.borrados.append(clave)
        if self.antes_borrar:
            self.antes_borrar()
        self.objetos.pop(clave, None)
        if self.despues_borrar:
            self.despues_borrar()


class MantenimientoPersistenteTests(SimpleTestCase):
    databases = {"default"}
    destino = ConfirmacionPersistenteTests.destino
    cuota = ConfirmacionPersistenteTests.cuota
    firmador = ConfirmacionPersistenteTests.firmador
    registrar = ConfirmacionPersistenteTests.registrar
    leer_archivo = ConfirmacionPersistenteTests.leer_archivo

    def setUp(self):
        ConfirmacionPersistenteTests.setUp(self)
        self.bucket = BucketMantenimiento()
        self.bucket.objetos[self.sesion.clave_temporal] = (b"12345", "text/plain")
        self.fabrica_bucket = Mock(return_value=self.bucket)
        self.verificador = Mock(side_effect=self.bucket.verificar)
        self.remoto_concluido = True  # Evidencia sintética; nunca derivada del reloj.
        self.proveedor.inspeccionar_objeto_tecnico = Mock(side_effect=self.inspeccionar)
        self.politica = PoliticaMantenimiento(margen_segundos=1, reintento_segundos=1,
            reintento_maximo_segundos=4, barrido_segundos=2, preparado_antiguo_segundos=2)

    def inspeccionar(self, *, sesion_id, organizacion_id, clave):
        assert connection.in_atomic_block, "Referencias sin coordinación SQL"
        with connection.cursor() as cursor:
            # Solo fixture: busca TODAS las referencias, incluso papelera/otro actor.
            cursor.execute("SELECT EXISTS(SELECT 1 FROM archivos WHERE clave_s3=%s)", [clave])
            referenciado = cursor.fetchone()[0]
        return InspeccionObjetoTecnico(sesion_id, organizacion_id, clave,
                                      referenciado, self.remoto_concluido)

    def confirmador(self):
        return ServicioConfirmacionCargas(
            servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=self.fabrica_bucket, verificador=self.verificador)

    def confirmar(self, **kwargs):
        return self.confirmador().confirmar(solicitante_id=self.actor,
            archivo_id=str(self.sesion.archivo_id), datos={}, **kwargs)

    def recuperar(self, **kwargs):
        return self.confirmador().confirmar(solicitante_id=kwargs["solicitante_id"],
            archivo_id=str(kwargs["archivo_id"]), datos={}, solo_recuperar=True)

    def servicio(self, **kwargs):
        opciones = dict(servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=self.fabrica_bucket, politica=self.politica, recuperador=self.recuperar)
        opciones.update(kwargs)
        return ServicioMantenimiento(**opciones)

    def vencer(self):
        SesionCarga.objects.filter(pk=self.sesion.pk).update(
            creado_en=timezone.now() - timedelta(minutes=5),
            expira_en=timezone.now() - timedelta(seconds=3))
        self.sesion.refresh_from_db()

    def debido(self):
        TrabajoMantenimiento.objects.filter(sesion=self.sesion).update(
            proximo_intento=timezone.now() - timedelta(seconds=1))

    def preparar(self):
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.org):
            return repo.preparar_publicacion(archivo_id=self.sesion.archivo_id,
                solicitante_id=self.actor, clave_final=nueva_clave_final(self.sesion.archivo_id),
                etag_origen='"sintetico"')

    def trabajo(self):
        return TrabajoMantenimiento.objects.get(sesion=self.sesion)

    def test_trigger_actualiza_fecha_y_conserva_ack_en_update_parcial(self):
        self.assertEqual(self.confirmar()["data"]["id"], str(self.sesion.archivo_id))
        original = self.trabajo()
        self.assertTrue(original.copia_concluida)
        fecha_pasada = timezone.now() - timedelta(days=1)
        TrabajoMantenimiento.objects.filter(sesion=self.sesion).update(
            fallos_consecutivos=1, actualizado_en=fecha_pasada)
        actual = self.trabajo()
        self.assertGreater(actual.actualizado_en, original.actualizado_en)
        self.assertGreater(actual.actualizado_en, fecha_pasada)
        self.assertEqual(actual.fallos_consecutivos, 1)
        self.assertTrue(actual.copia_concluida)
        self.assertEqual(actual.estado, original.estado)

    def test_cancelar_libera_una_vez_sin_borrar_bajo_url_vigente(self):
        servicio = self.servicio()
        respuesta = servicio.cancelar(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.assertEqual(respuesta, {"estado": "CANCELED", "pendiente_reconciliacion": False})
        servicio.cancelar(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.assertEqual(LogAuditoria.objects.filter(accion="CARGA_CANCELADA").count(), 1)
        self.assertEqual(LogAuditoria.objects.filter(accion="CANCELACION_SOLICITADA").count(), 1)
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.org):
            self.assertEqual(repo.bytes_pendientes(organizacion_id=self.org), 0)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)
        self.assertEqual(self.bucket.borrados, [])
        self.assertEqual(self.trabajo().causa, "URL_VIGENTE")

    def test_actor_ajeno_no_crea_solicitud_ni_usa_bucket(self):
        with self.assertRaises(SesionCarga.DoesNotExist):
            self.servicio().cancelar(solicitante_id=self.otro_actor, archivo_id=self.sesion.archivo_id)
        self.assertFalse(TrabajoMantenimiento.objects.exists())
        self.assertEqual(self.bucket.borrados, [])

    def test_cancelar_confirmado_no_resta_uso_ni_borra_final(self):
        self.confirmar()
        with self.assertRaises(EstadoIncompatible):
            self.servicio().cancelar(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)
        self.assertIn(nueva_clave_final(self.sesion.archivo_id), self.bucket.objetos)

    def test_vencimiento_y_borrado_sin_ledger_recuperables(self):
        self.vencer()
        informe = self.servicio().ejecutar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.EXPIRED)
        self.assertEqual(informe["resultados"], {"VERIFICADO": 1})
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)
        self.assertIsNotNone(self.trabajo().verificado_en)
        self.assertEqual(self.bucket.objetos, {})
        self.assertEqual(LogAuditoria.objects.filter(accion="CARGA_VENCIDA").count(), 1)
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(LogAuditoria.objects.filter(accion="CARGA_VENCIDA").count(), 1)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)

    def test_reserva_vencida_no_cuenta_con_scheduler_retrasado(self):
        self.vencer()
        self.assertEqual(self.servicio().metricas()["bytes_reservados_efectivos"], 0)
        self.assertEqual(self.servicio().metricas()["pendientes_vencidas"], 1)
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assertEqual(self.bucket.copias, 0)

    def test_confirmacion_publicada_limpia_solo_temporal(self):
        self.confirmar()
        self.assertTrue(self.trabajo().copia_concluida)
        self.remoto_concluido = False  # No exige evidencia ajena para el ACK propio.
        final = nueva_clave_final(self.sesion.archivo_id)
        self.vencer()
        self.servicio().ejecutar()
        self.assertEqual(self.bucket.borrados, [self.sesion.clave_temporal])
        self.assertIn(final, self.bucket.objetos)
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.PUBLISHED)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_put_tardio_reaparece_y_tombstone_programa_otro_barrido(self):
        self.vencer()
        self.servicio().ejecutar()
        self.bucket.objetos[self.sesion.clave_temporal] = (b"tarde", "text/plain")
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.bucket.objetos, {})
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.EXPIRED)
        self.assertGreater(self.trabajo().proximo_intento, timezone.now())
        with self.assertRaises(ErrorCarga):
            self.confirmar()

    def test_put_iniciado_reaparece_entre_delete_y_head_no_marca_limpiado(self):
        self.vencer()
        self.bucket.despues_borrar = lambda: self.bucket.objetos.update(
            {self.sesion.clave_temporal: (b"tarde", "text/plain")})
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.RETRY)
        self.assertIsNone(self.trabajo().verificado_en)

    def test_delete_timeout_sin_borrar_persiste_reintentos_con_espera_acotada(self):
        self.vencer()
        self.bucket.antes_borrar = Mock(side_effect=ErrorS3())
        for n in range(1, 7):
            self.debido()
            self.servicio().ejecutar()
            trabajo = self.trabajo()
            self.assertEqual(trabajo.fallos_consecutivos, n)
            self.assertEqual(trabajo.estado, EstadoMantenimiento.RETRY)
            self.assertEqual(trabajo.causa, "S3")
            self.assertLessEqual((trabajo.proximo_intento - timezone.now()).total_seconds(), 4)
        self.bucket.antes_borrar = None
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)

    def test_delete_timeout_despues_borrar_verifica_ausencia(self):
        self.vencer()
        self.bucket.despues_borrar = Mock(side_effect=ErrorS3())
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)

    def test_head_403_no_acredita_ausencia(self):
        self.vencer()
        self.bucket.consultar = Mock(side_effect=ErrorS3("acceso"))
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.RETRY)
        self.assertIsNone(self.trabajo().verificado_en)

    def test_caida_worker_despues_delete_deja_trabajo_durable(self):
        self.vencer()
        self.bucket.despues_borrar = Mock(side_effect=WorkerInterrumpido())
        with self.assertRaises(WorkerInterrumpido):
            self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.RETRY)
        self.assertGreater(self.trabajo().proximo_intento, timezone.now())
        self.bucket.despues_borrar = None
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)

    def test_fallo_auditoria_despues_delete_no_publica_falso_exito(self):
        self.vencer()
        def auditar(**kwargs):
            if kwargs["accion"] == "LIMPIEZA_VERIFICADA":
                raise OperationalError("synthetic-private-audit-secret")
            auditar_mantenimiento(**kwargs)
        self.servicio(auditoria=auditar).ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.RETRY)
        self.assertIsNone(self.trabajo().verificado_en)
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)
        self.assertNotIn("secret", str(list(LogAuditoria.objects.values_list("detalles", flat=True))))

    def test_fallo_auditoria_de_vencimiento_revierte_transicion(self):
        self.vencer()
        self.servicio(auditoria=Mock(side_effect=OperationalError("synthetic-private"))).ejecutar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.PENDING)
        self.assertEqual(self.bucket.borrados, [])
        self.assertEqual(self.trabajo().causa, "SQL")

    def test_proveedor_ausente_deja_pendiente_sin_bucket_y_recupera(self):
        self.vencer()
        self.servicio(servicios_factory=Mock(side_effect=ErrorCarga(CodigoError.SERVICE_UNAVAILABLE))).ejecutar()
        self.assertEqual(self.trabajo().causa, "DEPENDENCIA")
        self.fabrica_bucket.assert_not_called()
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)

    def test_proveedor_sin_inspeccion_no_usa_404_de_permisos_como_evidencia(self):
        self.vencer()
        del self.proveedor.inspeccionar_objeto_tecnico
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "DEPENDENCIA")
        self.assertEqual(self.bucket.borrados, [])
        self.proveedor.autorizar_descarga.assert_not_called()

    def test_evidencia_de_otra_clave_o_booleano_no_estricto_se_rechaza(self):
        self.vencer()
        original = self.inspeccionar
        for cambios in ({"clave": "cloudvault/dani/temporales/otro"}, {"referenciado": 0},
                        {"copia_concluida": 1}, {"sesion_id": uuid4()}):
            with self.subTest(cambios=cambios):
                self.proveedor.inspeccionar_objeto_tecnico.side_effect = lambda **kwargs: replace(
                    original(**kwargs), **cambios)
                self.debido()
                self.servicio().ejecutar()
                self.assertEqual(self.trabajo().causa, "INTEGRIDAD")
                self.assertEqual(self.bucket.borrados, [])

    def test_no_borrar_claves_ajenas_o_publicacion_de_otro_uuid(self):
        self.vencer()
        SesionCarga.objects.filter(pk=self.sesion.pk).update(clave_temporal="otros/objeto")
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "INTEGRIDAD")
        self.assertEqual(self.bucket.borrados, [])

    def test_ledger_con_clave_no_canonica_permanece_sin_borrar(self):
        intento = self.preparar()
        IntentoPublicacion.objects.filter(pk=intento.pk).update(clave_final=nueva_clave_final(uuid4()))
        self.vencer()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "INTEGRIDAD")
        self.assertEqual(self.bucket.borrados, [])

    def test_prepared_antiguo_y_head_ausente_no_prueban_copy_finalizado(self):
        intento = self.preparar()
        IntentoPublicacion.objects.filter(pk=intento.pk).update(creado_en=timezone.now()-timedelta(days=100))
        self.remoto_concluido = False
        self.vencer()
        informe = self.servicio().ejecutar()
        self.assertEqual(informe["metricas"]["prepared_antiguos"], 1)
        self.assertEqual(self.trabajo().causa, "COPY_AMBIGUO")
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.PENDING)
        self.assertEqual(self.bucket.borrados, [])
        self.assertEqual(self.bucket.consultas, 0)

    def test_cancelacion_con_copy_ambiguo_no_anuncia_liberacion(self):
        self.preparar()
        self.remoto_concluido = False
        resultado = self.servicio().cancelar(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.assertEqual(resultado, {"estado": "PENDING", "pendiente_reconciliacion": True})
        self.assertEqual(self.trabajo().causa, "COPY_AMBIGUO")
        self.assertEqual(self.bucket.borrados, [])

    def test_copy_con_evidencia_terminal_permite_abandono_y_limpieza(self):
        self.preparar()
        self.vencer()
        self.servicio().ejecutar()
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.EXPIRED)
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.CLEANED)
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)
        self.assertEqual(self.bucket.copias, 0)

    def test_final_fallido_con_referencia_en_papelera_no_se_borra(self):
        self.preparar()
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO archivos
                (id,organizacion_id,propietario_id,nombre_original,clave_s3,tamano_bytes,tipo_mime,en_papelera)
                VALUES (%s,%s,%s,'Otro',%s,5,'text/plain',TRUE)""",
                [uuid4(), self.otra_org, self.otro_actor, nueva_clave_final(self.sesion.archivo_id)])
        self.vencer()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "REFERENCIADO")
        self.assertEqual(self.bucket.borrados, [])

    def test_abandoned_no_es_prueba_de_ausencia_de_copy_remoto(self):
        self.preparar()
        IntentoPublicacion.objects.update(estado=EstadoPublicacion.ABANDONED)
        SesionCarga.objects.update(estado=EstadoSesion.CANCELED)
        self.vencer()
        self.remoto_concluido = False
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "COPY_AMBIGUO")
        self.assertEqual(self.bucket.borrados, [])

    def test_recuperar_copy_ambiguo_con_final_sin_repetir_copia(self):
        self.bucket.despues_copia = Mock(side_effect=ErrorS3())
        with self.assertRaises(ErrorS3):
            self.confirmar()
        self.assertFalse(self.trabajo().copia_concluida)
        self.remoto_concluido = False
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "COPY_AMBIGUO")
        self.remoto_concluido = True
        self.debido()
        informe = self.servicio().ejecutar()
        self.assertEqual(informe["resultados"], {"RECUPERADO": 1})
        self.assertEqual(self.bucket.copias, 1)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.CONFIRMED)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_recuperacion_sin_ledger_no_emite_copy(self):
        with self.assertRaises(IntegridadCarga):
            self.confirmar(solo_recuperar=True)
        self.assertEqual(self.bucket.copias, 0)
        self.fabrica_bucket.assert_not_called()

    def test_sin_recuperador_no_finge_publicacion(self):
        self.preparar()
        self.servicio(recuperador=None).ejecutar()
        self.assertEqual(self.trabajo().causa, "RECUPERACION")
        self.assertEqual(self.bucket.copias, 0)

    def test_trabajo_reconstruido_sin_entrega_a_cola(self):
        self.vencer()
        SesionCarga.objects.update(estado=EstadoSesion.EXPIRED)
        # Simula muerte justo después del commit, antes de registrar/encolar.
        self.assertFalse(TrabajoMantenimiento.objects.exists())
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)

    def test_tombstone_no_se_elimina_mientras_existe_trabajo(self):
        self.vencer()
        self.servicio().ejecutar()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM sesiones_carga WHERE id=%s", [self.sesion.pk])

    def test_conexion_perdida_durante_delete_no_marca_limpiado(self):
        self.vencer()
        self.bucket.despues_borrar = connection.close
        self.servicio().ejecutar()
        self.assertIsNone(self.trabajo().verificado_en)
        self.bucket.despues_borrar = None
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().estado, EstadoMantenimiento.VERIFIED)

    def test_transaccion_exterior_rechazada_antes_de_bucket(self):
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.servicio().ejecutar()
        self.fabrica_bucket.assert_not_called()

    def _en_hilo(self, accion):
        connections.close_all()
        try:
            return accion()
        finally:
            connections.close_all()

    def test_confirmacion_activa_excluye_limpieza_y_cancelacion(self):
        inicio, seguir = Event(), Event()
        def pausa():
            inicio.set()
            if not seguir.wait(5):
                raise RuntimeError("Fixture agotó espera")
        self.bucket.despues_copia = pausa
        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(self._en_hilo, self.confirmar)
            try:
                self.assertTrue(inicio.wait(5))
                self.servicio().ejecutar()
                with self.assertRaises(ErrorCarga):
                    self.servicio().cancelar(solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
                self.assertEqual(self.bucket.borrados, [])
            finally:
                seguir.set()
            futuro.result(timeout=5)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.CONFIRMED)
        self.assertEqual(self.bucket.copias, 1)

    def test_dos_workers_comparten_reclamo_y_no_borran_publicacion(self):
        self.confirmar()
        self.vencer()
        self.servicio().reconstruir()
        inicio, seguir = Event(), Event()
        def pausa():
            inicio.set()
            if not seguir.wait(5):
                raise RuntimeError("Fixture agotó espera")
        self.bucket.antes_borrar = pausa
        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(self._en_hilo, lambda: self.servicio().procesar(self.sesion.pk))
            try:
                self.assertTrue(inicio.wait(5))
                self.servicio().procesar(self.sesion.pk)
            finally:
                seguir.set()
            self.assertEqual(futuro.result(timeout=5), "VERIFICADO")
        self.assertEqual(self.bucket.borrados, [self.sesion.clave_temporal])
        self.assertIn(nueva_clave_final(self.sesion.archivo_id), self.bucket.objetos)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 85)

    def test_cancelacion_activa_impide_confirmacion_concurrente(self):
        inicio, seguir = Event(), Event()
        def auditar(**kwargs):
            if kwargs["accion"] == "CANCELACION_SOLICITADA":
                inicio.set()
                if not seguir.wait(5):
                    raise RuntimeError("Fixture agotó espera")
            auditar_mantenimiento(**kwargs)
        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(self._en_hilo, lambda: self.servicio(auditoria=auditar).cancelar(
                solicitante_id=self.actor, archivo_id=self.sesion.archivo_id))
            try:
                self.assertTrue(inicio.wait(5))
                with self.assertRaises(ErrorCarga):
                    self.confirmar()
            finally:
                seguir.set()
            self.assertEqual(futuro.result(timeout=5)["estado"], "CANCELED")
        self.assertEqual(self.bucket.copias, 0)

    def test_proceso_periodico_real_dos_ciclos_sin_env_ni_broker(self):
        self.vencer()
        inicio = time.monotonic()
        resultado = subprocess.run([sys.executable, "-m", "django", "mantener_cargas",
            "--continuo", "--intervalo", "1", "--ciclos", "2",
            "--settings=almacenamiento.tests_persistencia.settings"],
            env={**os.environ, "ALMACENAMIENTO_SERVICIOS_FACTORY": ""},
            capture_output=True, text=True, timeout=15)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        informes = [json.loads(linea) for linea in resultado.stdout.splitlines()]
        self.assertEqual([i["ciclo"] for i in informes], [1, 2])
        self.assertGreaterEqual(time.monotonic() - inicio, 1)
        self.assertEqual(informes[0]["intervalo_segundos"], 1)
        self.assertEqual(informes[0]["resultados"], {"DEPENDENCIA": 1})
        self.assertEqual(self.trabajo().causa, "DEPENDENCIA")

    def test_copy_acusado_por_sdk_limpia_final_invalido_sin_evidencia_ajena(self):
        self.bucket.antes_copia = lambda: self.bucket.objetos.update(
            {self.sesion.clave_temporal: (b"123456", "text/plain")})
        with self.assertRaises(ErrorCarga):
            self.confirmar()
        self.assertTrue(self.trabajo().copia_concluida)
        self.remoto_concluido = False
        self.vencer()
        self.debido()
        self.servicio().ejecutar()
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.CLEANED)
        self.assertEqual(self.bucket.objetos, {})

    def test_fallo_persistir_ack_deja_prepared_y_no_repite_copy(self):
        from unittest.mock import patch
        original = TrabajoMantenimiento.save
        def guardar(trabajo, **kwargs):
            if trabajo.copia_concluida is True:
                raise OperationalError("synthetic-private-ack")
            original(trabajo, **kwargs)
        with patch.object(TrabajoMantenimiento, "save", guardar), self.assertRaises(OperationalError):
            self.confirmar()
        self.assertFalse(self.trabajo().copia_concluida)
        self.remoto_concluido = False
        self.servicio().ejecutar()
        self.assertEqual(self.trabajo().causa, "COPY_AMBIGUO")
        self.assertEqual(self.bucket.copias, 1)

    def test_fallo_auditoria_cancelacion_revierte_solicitud_y_reserva(self):
        with self.assertRaises(OperationalError):
            self.servicio(auditoria=Mock(side_effect=OperationalError("synthetic-private"))).cancelar(
                solicitante_id=self.actor, archivo_id=self.sesion.archivo_id)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, EstadoSesion.PENDING)
        self.assertFalse(TrabajoMantenimiento.objects.exists())
