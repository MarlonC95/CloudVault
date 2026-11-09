"""Fase 4 con reloj y repositorios sustituidos: sin BD, .env, red o scheduler."""

import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from almacenamiento.persistencia import ReclamoOcupado
from almacenamiento.s3 import ErrorS3
from storage.papelera import ErrorPapelera, ServicioPapelera
from storage.repositorio_papelera import CandidatoPurga, RepositorioPapelera


AHORA = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
CORTE = AHORA - timedelta(days=30)
RUTA_COMANDO = "storage.management.commands.purgar_papelera"


def candidato(*, fecha=CORTE, recuperacion=False):
    return CandidatoPurga(uuid4(), uuid4(), fecha, str(uuid4()),
                          "cloudvault/dani/publicaciones/ejemplo",
                          str(uuid4()) if recuperacion else None, recuperacion)


def archivo_de(seleccion):
    return SimpleNamespace(pk=seleccion.archivo_id,
                           organizacion_id=seleccion.organizacion_id,
                           en_papelera=True, fecha_papelera=seleccion.fecha_papelera,
                           clave_s3=seleccion.clave_s3)


class ComandoPurgaAutomaticaTests(SimpleTestCase):
    def invocar(self, seleccion, *, ejecutar=False, resultados=None, **opciones):
        salida = StringIO()
        repo = MagicMock()
        repo.seleccionar_candidatos_purga.return_value = seleccion
        with patch(RUTA_COMANDO + ".RepositorioPapelera", return_value=repo) as factory, \
             patch(RUTA_COMANDO + ".ServicioPapelera") as servicio, \
             patch(RUTA_COMANDO + ".ClienteS3") as s3, \
             patch(RUTA_COMANDO + ".timezone.now", return_value=AHORA) as reloj:
            if resultados is not None:
                servicio.return_value.purgar_automaticamente.side_effect = resultados
            error = None
            try:
                call_command("purgar_papelera", ejecutar=ejecutar,
                             stdout=salida, **opciones)
            except CommandError as exc:
                error = exc
        texto = salida.getvalue().strip()
        return SimpleNamespace(resumen=json.loads(texto) if texto else None,
                               repo=repo, factory=factory, servicio=servicio,
                               s3=s3, reloj=reloj, error=error)

    def test_simulacion_predeterminada_no_construye_servicio_o_s3(self):
        org = uuid4()
        resultado = self.invocar([candidato(), candidato(recuperacion=True)],
                                 limite=7, organizacion_id=str(org))
        self.assertIsNone(resultado.error)
        resultado.servicio.assert_not_called()
        resultado.s3.assert_not_called()
        resultado.repo.seleccionar_candidatos_purga.assert_called_once_with(
            corte=CORTE, ahora=AHORA, limite=7, organizacion_id=org)
        resultado.reloj.assert_called_once_with()
        self.assertEqual(resultado.resumen["modo"], "simulacion")
        self.assertEqual(resultado.resumen["candidatos_nuevos"], 1)
        self.assertEqual(resultado.resumen["recuperaciones"], 1)
        self.assertEqual(resultado.resumen["completados"], 0)
        self.assertEqual(resultado.resumen["bytes_fisicos_purgados"], 0)
        self.assertEqual(resultado.resumen["cuota_liberada_bytes"], 0)
        self.assertNotIn("cloudvault/dani", json.dumps(resultado.resumen))

    def test_ejecucion_delega_cada_recurso_y_suma_solo_bytes_confirmados(self):
        seleccion = [candidato(), candidato(recuperacion=True)]
        resultado = self.invocar(seleccion, ejecutar=True, resultados=[11, 0])
        self.assertIsNone(resultado.error)
        self.assertEqual(resultado.servicio.return_value.purgar_automaticamente.call_count, 2)
        for llamada, esperado in zip(
                resultado.servicio.return_value.purgar_automaticamente.call_args_list,
                seleccion, strict=True):
            self.assertIs(llamada.kwargs["candidato"], esperado)
            self.assertTrue(callable(llamada.kwargs["crear_cliente"]))
        self.assertEqual(resultado.resumen["completados"], 2)
        self.assertEqual(resultado.resumen["bytes_fisicos_purgados"], 11)
        self.assertEqual(resultado.resumen["cuota_liberada_bytes"], 0)

    def test_fallo_ocupado_y_snapshot_obsoleto_no_impiden_procesar_otro(self):
        resultado = self.invocar(
            [candidato() for _ in range(4)], ejecutar=True,
            resultados=[ErrorPapelera(), 13,
                        ErrorPapelera("CANDIDATE_STALE", 409),
                        ErrorPapelera("RESOURCE_BUSY", 409)])
        self.assertIsInstance(resultado.error, CommandError)
        self.assertEqual(resultado.servicio.return_value.purgar_automaticamente.call_count, 4)
        self.assertEqual(resultado.resumen["completados"], 1)
        self.assertEqual(resultado.resumen["omitidos"], 1)
        self.assertEqual(resultado.resumen["ocupados"], 1)
        self.assertEqual(resultado.resumen["reintentables"], 1)
        self.assertEqual(resultado.resumen["bytes_fisicos_purgados"], 13)

    def test_recurso_incompatible_y_reintento_diferido_salen_del_resumen(self):
        resultado = self.invocar(
            [candidato(), candidato()], ejecutar=True,
            resultados=[ErrorPapelera("PURGE_INCOMPATIBLE", 409),
                        ErrorPapelera("RETRY_DEFERRED", 409)])
        self.assertIsInstance(resultado.error, CommandError)
        self.assertEqual(resultado.resumen["incompatibles"], 1)
        self.assertEqual(resultado.resumen["diferidos"], 1)
        self.assertEqual(resultado.resumen["reintentables"], 0)

    def test_limites_y_organizacion_invalidos_no_consultan_repositorio(self):
        for limite in (0, -1, 101):
            with self.subTest(limite=limite), patch(RUTA_COMANDO + ".RepositorioPapelera") as repo:
                with self.assertRaises(CommandError):
                    call_command("purgar_papelera", limite=limite, stdout=StringIO())
                repo.assert_not_called()
        with patch(RUTA_COMANDO + ".RepositorioPapelera") as repo:
            with self.assertRaises(CommandError):
                call_command("purgar_papelera", organizacion_id="no-uuid", stdout=StringIO())
            repo.assert_not_called()


class SeleccionYReintentosPurgaTests(SimpleTestCase):
    def setUp(self):
        self.repo = RepositorioPapelera()

    def test_treinta_dias_es_un_limite_inclusivo_de_instante(self):
        for desfase, esperado in ((-timedelta(microseconds=1), True),
                                  (timedelta(0), True),
                                  (timedelta(microseconds=1), False)):
            seleccion = candidato(fecha=CORTE + desfase)
            with self.subTest(desfase=desfase), patch.object(
                    self.repo, "ultimo_evento", return_value=SimpleNamespace(
                        detalles={"generacion_id":seleccion.generacion_id})):
                self.assertEqual(self.repo.validar_candidato(
                    archivo_de(seleccion), seleccion, AHORA), esperado)

    def test_cambios_de_snapshot_rechazan_sin_adoptar_datos_nuevos(self):
        seleccion = candidato()
        cambios = ({"organizacion_id":uuid4()}, {"pk":uuid4()},
                   {"fecha_papelera":CORTE + timedelta(days=1)},
                   {"clave_s3":"otra"}, {"en_papelera":False},
                   {"fecha_papelera":None})
        for cambio in cambios:
            archivo = archivo_de(seleccion)
            vars(archivo).update(cambio)
            with self.subTest(cambio=cambio), patch.object(self.repo, "ultimo_evento") as evento:
                self.assertFalse(self.repo.validar_candidato(archivo, seleccion, AHORA))
                evento.assert_not_called()
        with patch.object(self.repo, "ultimo_evento", return_value=SimpleNamespace(
                detalles={"generacion_id":str(uuid4())})):
            self.assertFalse(self.repo.validar_candidato(archivo_de(seleccion), seleccion, AHORA))

    def test_recuperacion_manual_no_espera_treinta_dias_y_exige_misma_operacion(self):
        seleccion = candidato(fecha=AHORA - timedelta(days=2), recuperacion=True)
        detalles = {"operacion_id":seleccion.operacion_id,
                    "generacion_id":seleccion.generacion_id,
                    "fecha_papelera":seleccion.fecha_papelera.isoformat(),
                    "clave_s3":seleccion.clave_s3}
        with patch.object(self.repo, "ultimo_evento", return_value=SimpleNamespace(
                detalles={"generacion_id":seleccion.generacion_id})), \
             patch.object(self.repo, "intencion_pendiente", return_value=SimpleNamespace(detalles=detalles)):
            self.assertTrue(self.repo.validar_candidato(archivo_de(seleccion), seleccion, AHORA))
            self.assertFalse(self.repo.validar_candidato(
                archivo_de(seleccion), replace(seleccion, operacion_id=str(uuid4())), AHORA))

    def test_espera_de_reintento_respeta_instante_inclusivo(self):
        intencion = {"operacion_id":str(uuid4()), "generacion_id":str(uuid4())}
        for fecha, esperado in ((AHORA - timedelta(seconds=1), True),
                                (AHORA, True), (AHORA + timedelta(seconds=1), False)):
            consulta = MagicMock()
            consulta.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
                detalles={"reintentar_en":fecha.isoformat()})
            with self.subTest(fecha=fecha), patch.object(self.repo, "_eventos_archivo", return_value=consulta):
                self.assertEqual(self.repo.reintento_purga_vencido(object(), intencion, AHORA), esperado)

    def test_auditoria_de_reintentos_aplica_backoff_y_tope_sin_mensajes_privados(self):
        intencion = {"operacion_id":str(uuid4()), "generacion_id":str(uuid4())}
        for anterior, minutos in ((0, 1), (1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 60), (100, 60)):
            consulta = MagicMock()
            consulta.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
                detalles={"intento":anterior, "bytes_fisicos_confirmados":7})
            with self.subTest(anterior=anterior), \
                 patch.object(self.repo, "_eventos_archivo", return_value=consulta), \
                 patch.object(self.repo, "_crear_evento") as crear:
                detalles = self.repo.auditar_reintento_purga(
                    object(), None, intencion, "mensaje-privado-proveedor", ahora=AHORA)
            self.assertEqual(detalles["intento"], anterior + 1)
            self.assertEqual(detalles["reintentar_en"], (AHORA + timedelta(minutes=minutos)).isoformat())
            self.assertEqual(detalles["motivo"], "S3")
            self.assertEqual(detalles["bytes_fisicos_confirmados"], 7)
            self.assertEqual(crear.call_args.args[2], "PAPELERA_PURGA_REINTENTO")
            self.assertNotIn("mensaje-privado", json.dumps(detalles))

    def test_selector_usa_filtro_inclusivo_orden_y_tope_sin_modificar_filas(self):
        org = uuid4()
        filas = MagicMock()
        filas.filter.return_value = filas
        filas.count.return_value = 0
        filas.order_by.return_value.values.return_value.__getitem__.return_value = []
        eventos = MagicMock()
        eventos.filter.return_value = eventos
        eventos.count.return_value = 0
        eventos.order_by.return_value.__getitem__.return_value = []
        with patch("storage.repositorio_papelera.Archivo.objects") as archivos, \
             patch("storage.repositorio_papelera.LogAuditoria.objects") as auditoria:
            archivos.using.return_value.filter.return_value = filas
            auditoria.using.return_value.filter.return_value = eventos
            resultado = self.repo.seleccionar_candidatos_purga(
                corte=CORTE, ahora=AHORA, limite=8, organizacion_id=org)
        self.assertEqual(resultado, [])
        archivos.using.return_value.filter.assert_any_call(
            en_papelera=True, fecha_papelera__isnull=False, fecha_papelera__lte=CORTE)
        archivos.using.return_value.create.assert_not_called()
        auditoria.using.return_value.create.assert_not_called()

    def test_selector_rotates_bounded_scan_between_quarter_hours(self):
        org = uuid4()
        filas = MagicMock()
        filas.filter.return_value = filas
        filas.count.return_value = 5000
        filas.order_by.return_value.values.return_value.__getitem__.return_value = []
        eventos = MagicMock()
        eventos.filter.return_value = eventos
        eventos.count.return_value = 0
        with patch("storage.repositorio_papelera.Archivo.objects") as archivos, \
             patch("storage.repositorio_papelera.LogAuditoria.objects") as auditoria:
            archivos.using.return_value.filter.return_value = filas
            auditoria.using.return_value.filter.return_value = eventos
            for ahora in (AHORA, AHORA + timedelta(minutes=15)):
                self.repo.seleccionar_candidatos_purga(
                    corte=CORTE, ahora=ahora, limite=8, organizacion_id=org)
        paginas = filas.order_by.return_value.values.return_value.__getitem__.call_args_list
        self.assertEqual(paginas[0].args[0].stop - paginas[0].args[0].start, 100)
        self.assertNotEqual(paginas[0].args[0].start, paginas[1].args[0].start)


class RepositorioAutomaticoFalso:
    def __init__(self, seleccion):
        self.fila = archivo_de(seleccion)
        self.nivel = MagicMock(side_effect=AssertionError("La tarea no suplanta un miembro"))
        self.validar_candidato = MagicMock(return_value=True)
        self.validar_identidad_candidato = MagicMock(return_value=True)
        self.reintento_candidato_vencido = MagicMock(return_value=False)
        self.generar_o_reutilizar_intencion = MagicMock(return_value={
            "operacion_id":seleccion.operacion_id or str(uuid4()),
            "clave_s3":seleccion.clave_s3})
        self.referencia_incompatible = MagicMock(return_value=False)
        self.cerrar_purga = MagicMock()
        self.auditar_reintento_purga = MagicMock()

    @contextmanager
    def reclamar(self, archivo_id):
        yield lambda: None

    @contextmanager
    def transaccion(self, org):
        yield

    def archivo(self, archivo_id, org):
        return self.fila


class ServicioPurgaAutomaticaTests(SimpleTestCase):
    def test_lock_ocupado_conserva_respuesta_http_service_unavailable(self):
        repo = RepositorioAutomaticoFalso(candidato())

        @contextmanager
        def ocupado(_archivo_id):
            raise ReclamoOcupado()
            yield

        repo.reclamar = ocupado
        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
        with self.assertRaises(ErrorPapelera) as error:
            with servicio.reclamar(repo.fila.pk):
                pass
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail["error"]["code"], "SERVICE_UNAVAILABLE")
        self.assertTrue(error.exception.es_reclamo_ocupado)

    def test_automatico_delega_flujo_unico_y_origen_sin_autorizar_actor_ficticio(self):
        seleccion = candidato()
        repo = RepositorioAutomaticoFalso(seleccion)
        cliente = MagicMock()
        cliente.borrar_fisico_verificado.return_value = 17
        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
        self.assertEqual(servicio.purgar_automaticamente(candidato=seleccion, cliente=cliente), 17)
        repo.nivel.assert_not_called()
        repo.validar_candidato.assert_called_once_with(repo.fila, seleccion, AHORA)
        self.assertEqual(repo.generar_o_reutilizar_intencion.call_args.kwargs, {"origen":"VENCIMIENTO"})
        self.assertIsNone(repo.generar_o_reutilizar_intencion.call_args.args[1])
        repo.cerrar_purga.assert_called_once()

    def test_recuperacion_revalida_backoff_despues_de_tomar_reclamo(self):
        seleccion = candidato(recuperacion=True)
        repo = RepositorioAutomaticoFalso(seleccion)
        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
        crear = MagicMock()
        with self.assertRaises(ErrorPapelera) as error:
            servicio.purgar_automaticamente(candidato=seleccion, crear_cliente=crear)
        self.assertEqual(error.exception.codigo, "RETRY_DEFERRED")
        repo.validar_identidad_candidato.assert_called_once_with(repo.fila, seleccion)
        repo.reintento_candidato_vencido.assert_called_once_with(repo.fila, seleccion, AHORA)
        repo.generar_o_reutilizar_intencion.assert_not_called()
        crear.assert_not_called()

    def test_s3_incompatible_queda_auditado_y_no_se_presenta_como_transitorio(self):
        seleccion = candidato()
        repo = RepositorioAutomaticoFalso(seleccion)
        cliente = MagicMock()
        cliente.borrar_fisico_verificado.side_effect = ErrorS3("incompatible")
        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
        with self.assertRaises(ErrorPapelera) as error:
            servicio.purgar_automaticamente(candidato=seleccion, cliente=cliente)
        self.assertEqual(error.exception.codigo, "PURGE_INCOMPATIBLE")
        repo.auditar_reintento_purga.assert_called_once()
        self.assertEqual(repo.auditar_reintento_purga.call_args.args[3], "INCOMPATIBLE")
        repo.cerrar_purga.assert_not_called()

    def test_error_s3_manual_conserva_contrato_service_unavailable(self):
        seleccion = candidato()
        repo = RepositorioAutomaticoFalso(seleccion)
        repo.nivel = MagicMock(return_value=0)
        cliente = MagicMock()
        cliente.borrar_fisico_verificado.side_effect = ErrorS3("incompatible")
        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
        with self.assertRaises(ErrorPapelera) as error:
            servicio.purgar(solicitante_id=uuid4(), organizacion_id=seleccion.organizacion_id,
                             archivo_id=seleccion.archivo_id, cliente=cliente)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail["error"]["code"], "SERVICE_UNAVAILABLE")

    def test_snapshot_obsoleto_no_crea_intencion_ni_cliente(self):
        seleccion = candidato()
        for estado in ("cambio", "restaurado", "retirado"):
            repo = RepositorioAutomaticoFalso(seleccion)
            repo.validar_candidato.return_value = False
            if estado == "restaurado":
                repo.fila.en_papelera = False
            if estado == "retirado":
                repo.fila = None
            crear = MagicMock()
            servicio = ServicioPapelera(repositorio=repo, reloj=lambda: AHORA)
            with self.subTest(estado=estado), self.assertRaises(ErrorPapelera) as error:
                servicio.purgar_automaticamente(candidato=seleccion, crear_cliente=crear)
            self.assertEqual(error.exception.codigo, "CANDIDATE_STALE")
            repo.generar_o_reutilizar_intencion.assert_not_called()
            crear.assert_not_called()
