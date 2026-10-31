"""Reglas síncronas de lotes de carpeta; dobles sin base de datos ni S3."""

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, PermissionDenied

from auth_workspaces.models import LogAuditoria
from storage.lotes_papelera import ServicioLotesCarpeta
from storage.models import Archivo, Carpeta
from storage.papelera import ErrorPapelera
from storage.repositorio_papelera import RepositorioPapelera


AHORA = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


class RepoFalso:
    using = "default"

    def __init__(self):
        self.actor, self.org = uuid4(), uuid4()
        self.auditar = MagicMock()
        self.ultimo_evento = MagicMock()
        self.permisos = MagicMock(return_value=[])
        self.purga_pendiente = MagicMock(return_value=False)
        self.lote_purga_pendiente = MagicMock(return_value=False)
        self.nivel = MagicMock(return_value=0)
        self.capacidad = MagicMock(return_value=(1000, 0, 0))
        self.nombre_disponible = MagicMock(return_value=True)
        self.evento_restauracion = MagicMock()
        self.reclamos = []
        self.filas_transaccionales = []

    @contextmanager
    def reclamar(self, archivo_id):
        self.reclamos.append(archivo_id)
        yield lambda: None

    @contextmanager
    def transaccion(self, org):
        campos = ("en_papelera", "fecha_papelera", "padre_id", "carpeta_id")
        instantanea = [{campo: getattr(fila, campo, None) for campo in campos}
                       for fila in self.filas_transaccionales]
        try:
            yield
        except Exception:
            for fila, valores in zip(self.filas_transaccionales, instantanea, strict=True):
                for campo, valor in valores.items():
                    if hasattr(fila, campo):
                        setattr(fila, campo, valor)
            raise


class LotesCarpetaTests(SimpleTestCase):
    def _restaurar_lote(self, *, capacidad=(100, 60, 15), colision=False,
                        fallo_auditoria=False, miembro_restaurado_aparte=False,
                        nivel=0, padre_raiz=False, permiso_destino=True):
        repo = RepoFalso()
        raiz_id, archivo_id = uuid4(), uuid4()
        fecha = AHORA
        padre = (Carpeta(pk=uuid4(), organizacion_id=repo.org, padre_id=None,
                         nombre="Unidad", en_papelera=False) if padre_raiz else None)
        raiz = Carpeta(pk=raiz_id, organizacion_id=repo.org,
                       padre_id=padre.pk if padre else None,
                       nombre="Proyecto", en_papelera=True, fecha_papelera=fecha)
        raiz.save = MagicMock()
        archivo = Archivo(pk=archivo_id, organizacion_id=repo.org, propietario_id=repo.actor,
                          carpeta_id=raiz_id, nombre="datos.csv", clave_s3="objeto",
                          tamano_bytes=25, tipo_mime="text/csv", en_papelera=True,
                          fecha_papelera=fecha)
        archivo.save = MagicMock()
        independiente = Archivo(pk=uuid4(), organizacion_id=repo.org,
                                propietario_id=repo.actor, carpeta_id=raiz_id,
                                nombre="anterior.txt", clave_s3="anterior",
                                tamano_bytes=30, tipo_mime="text/plain",
                                en_papelera=True,
                                fecha_papelera=datetime(2026, 10, 20, 9,
                                                        tzinfo=timezone.utc))
        independiente.save = MagicMock()
        evento = SimpleNamespace(pk=1)
        miembros = [
            {"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
             "generacion_id": "gen-raiz",
             "padre_id": str(padre.pk) if padre else None, "nombre": "Proyecto"},
            {"tipo_elemento": "archivo", "recurso_id": str(archivo_id),
             "generacion_id": "gen-archivo", "padre_id": str(raiz_id),
             "nombre": "datos.csv", "tamano_bytes": 25},
        ]
        restaurado_aparte = SimpleNamespace(en_papelera=False, fecha_papelera=None,
                                             save=MagicMock())
        if miembro_restaurado_aparte:
            miembros.append({"tipo_elemento": "archivo", "recurso_id": str(uuid4()),
                             "generacion_id": "gen-aparte", "padre_id": str(raiz_id),
                             "nombre": "ya-restaurado.csv", "tamano_bytes": 10})
        manifiesto = {"version": 1, "cerrado": True, "operacion_id": "lote-1",
                      "raiz_id": str(raiz_id), "raiz_generacion_id": "gen-raiz",
                      "miembros": miembros}
        repo.ultimo_evento.return_value = SimpleNamespace(
            detalles={"generacion_id": "gen-archivo"})
        repo.capacidad.return_value = capacidad
        repo.nivel.return_value = nivel
        if nivel == 3:
            repo.permisos.side_effect = [["write"], ["write"], ["write"],
                                         ["write"] if permiso_destino else []]
        repo.nombre_disponible.side_effect = [True, not colision]
        repo.filas_transaccionales = [raiz, archivo]
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        carpetas, archivos, auditoria = MagicMock(), MagicMock(), MagicMock()
        carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.side_effect = [
            raiz, raiz]
        if padre:
            carpetas.using.return_value.filter.return_value.first.side_effect = [padre, padre]
        archivos.using.return_value.select_for_update.return_value.filter.return_value.first.side_effect = (
            [archivo, None] if miembro_restaurado_aparte else [archivo])
        auditoria.using.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            detalles=manifiesto)
        if fallo_auditoria:
            auditoria.using.return_value.create.side_effect = DatabaseError("fallo sintético")

        with patch.object(servicio, "_manifiesto", return_value=(evento, manifiesto)), \
             patch.object(Carpeta, "objects", carpetas), \
             patch.object(Archivo, "objects", archivos), \
             patch.object(LogAuditoria, "objects", auditoria):
            error = None
            try:
                resultado = servicio.restaurar(solicitante_id=repo.actor,
                                               organizacion_id=repo.org,
                                               carpeta_id=raiz_id)
            except (ErrorPapelera, NotFound, PermissionDenied) as exc:
                resultado, error = None, exc

        return SimpleNamespace(repo=repo, raiz=raiz, archivo=archivo,
                               independiente=independiente, restaurado_aparte=restaurado_aparte,
                               auditoria=auditoria, archivos=archivos,
                               resultado=resultado, error=error)

    def test_envio_registra_manifiesto_y_transiciona_solo_activos(self):
        repo = RepoFalso()
        carpeta_id, archivo_id = uuid4(), uuid4()
        previo_id = uuid4()
        fecha_previa = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        raiz = SimpleNamespace(pk=carpeta_id, organizacion_id=repo.org,
                               padre_id=None, nombre="Proyecto", en_papelera=False,
                               save=MagicMock())
        archivo = SimpleNamespace(pk=archivo_id, organizacion_id=repo.org,
                                  carpeta_id=carpeta_id, nombre="datos.csv",
                                  clave_s3="objeto", tamano_bytes=25,
                                  en_papelera=False, fecha_papelera=None,
                                  save=MagicMock())
        previo = SimpleNamespace(pk=previo_id, organizacion_id=repo.org,
                                 carpeta_id=carpeta_id, nombre="anterior.txt",
                                 clave_s3="objeto-anterior", tamano_bytes=30,
                                 en_papelera=True, fecha_papelera=fecha_previa,
                                 save=MagicMock())
        servicio = ServicioLotesCarpeta(
            repo=repo, reloj=lambda: AHORA,
            nuevo_id=MagicMock(side_effect=[uuid4(), uuid4(), uuid4()]),
        )
        with patch.object(servicio, "_arbol", return_value=(raiz, {carpeta_id: raiz},
                                                             {archivo_id: archivo, previo_id: previo})), \
             patch.object(LogAuditoria, "objects", MagicMock()) as auditoria:
            servicio.enviar(solicitante_id=repo.actor, organizacion_id=repo.org,
                            carpeta_id=carpeta_id)

        self.assertTrue(raiz.en_papelera)
        self.assertTrue(archivo.en_papelera)
        self.assertEqual(archivo.fecha_papelera, AHORA)
        self.assertEqual(set(repo.reclamos), {archivo_id, previo_id})
        self.assertEqual(previo.fecha_papelera, fecha_previa)
        previo.save.assert_not_called()
        repo.auditar.assert_called_once()
        llamada = auditoria.using.return_value.create.call_args
        self.assertEqual(llamada.kwargs["accion"], "PAPELERA_CARPETA_ENVIADA")
        manifiesto = llamada.kwargs["detalles"]
        self.assertTrue(manifiesto["cerrado"])
        self.assertEqual(manifiesto["raiz_id"], str(carpeta_id))
        self.assertEqual({m["recurso_id"] for m in manifiesto["miembros"]},
                         {str(carpeta_id), str(archivo_id)})

    def test_rol_operativo_rechazado_antes_de_mutar(self):
        repo = RepoFalso()
        repo.nivel.return_value = 2
        carpeta_id = uuid4()
        raiz = SimpleNamespace(pk=carpeta_id, organizacion_id=repo.org,
                               padre_id=None, nombre="Proyecto", en_papelera=False,
                               save=MagicMock())
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        with patch.object(servicio, "_arbol", return_value=(raiz, {carpeta_id: raiz}, {})), \
             self.assertRaises(PermissionDenied):
            servicio.enviar(solicitante_id=repo.actor, organizacion_id=repo.org,
                            carpeta_id=carpeta_id)
        raiz.save.assert_not_called()
        repo.auditar.assert_not_called()

    def test_envio_de_nivel_tres_sin_acl_se_rechaza_antes_de_mutar(self):
        repo = RepoFalso()
        repo.nivel.return_value = 3
        carpeta_id = uuid4()
        raiz = SimpleNamespace(pk=carpeta_id, organizacion_id=repo.org,
                               padre_id=None, nombre="Proyecto", en_papelera=False,
                               save=MagicMock())
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        with patch.object(servicio, "_arbol", return_value=(raiz, {carpeta_id: raiz}, {})), \
             self.assertRaises(NotFound):
            servicio.enviar(solicitante_id=repo.actor, organizacion_id=repo.org,
                            carpeta_id=carpeta_id)

        raiz.save.assert_not_called()
        repo.auditar.assert_not_called()

    def test_vaciado_vacio_cierra_seleccion_sin_purgar_ni_crear_s3(self):
        repo = RepoFalso()
        auditoria, archivos, carpetas = MagicMock(), MagicMock(), MagicMock()
        auditoria.using.return_value.filter.return_value.exists.return_value = False
        archivos.using.return_value.select_for_update.return_value.filter.return_value.order_by.return_value = []
        carpetas.using.return_value.select_for_update.return_value.filter.return_value.order_by.return_value = []
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        crear_cliente = MagicMock()
        with patch.object(LogAuditoria, "objects", auditoria), \
             patch("storage.lotes_papelera.Archivo.objects", archivos), \
             patch("storage.lotes_papelera.Carpeta.objects", carpetas), \
             patch("storage.papelera.ServicioPapelera") as purga:
            operacion = servicio.vaciar(solicitante_id=repo.actor,
                                        organizacion_id=repo.org,
                                        crear_cliente=crear_cliente)

        self.assertIsNotNone(operacion)
        acciones = [llamada.kwargs["accion"] for llamada in auditoria.using.return_value.create.call_args_list]
        self.assertEqual(acciones, ["PAPELERA_VACIADO_INICIADO", "PAPELERA_VACIADO_CERRADO"])
        purga.return_value.purgar.assert_not_called()
        crear_cliente.assert_not_called()

    def test_reintento_vaciado_reconoce_archivo_cerrado_y_completa_el_pendiente(self):
        repo = RepoFalso()
        operacion, archivo_cerrado, archivo_pendiente, archivo_nuevo = (
            uuid4(), uuid4(), uuid4(), uuid4())
        seleccion = {"version": 1, "operacion_id": str(operacion), "tipo_elemento": "vaciado",
                     "miembros": [
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_cerrado),
                          "generacion_id": "gen-a", "fecha_papelera": AHORA.isoformat()},
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_pendiente),
                          "generacion_id": "gen-b", "fecha_papelera": AHORA.isoformat()},
                     ]}
        evento = SimpleNamespace(detalles=seleccion)
        archivo = SimpleNamespace(pk=archivo_pendiente, organizacion_id=repo.org,
                                  en_papelera=True, fecha_papelera=AHORA)
        repo.ultimo_evento.return_value = SimpleNamespace(detalles={"generacion_id": "gen-b"})
        auditoria = MagicMock()
        cerrada, purgada = MagicMock(), MagicMock()
        cerrada.exists.return_value = False
        purgada.exists.return_value = True

        def buscar_eventos(**filtros):
            if filtros.get("accion") == "PAPELERA_VACIADO_INICIADO":
                return SimpleNamespace(first=lambda: evento)
            if filtros.get("accion") == "PAPELERA_VACIADO_CERRADO":
                return cerrada
            if filtros.get("accion") == "PAPELERA_PURGADO":
                return purgada
            return MagicMock()

        auditoria.using.return_value.filter.side_effect = buscar_eventos
        archivos = MagicMock()
        archivos.using.return_value.filter.return_value.first.side_effect = [None, archivo]
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        crear_cliente = MagicMock()
        with patch.object(LogAuditoria, "objects", auditoria), \
             patch("storage.lotes_papelera.Archivo.objects", archivos), \
             patch("storage.papelera.ServicioPapelera") as purga_comun:
            resultado = servicio.vaciar(
                solicitante_id=repo.actor, organizacion_id=repo.org,
                operacion_id=operacion, crear_cliente=crear_cliente)

        self.assertEqual(resultado, str(operacion))
        ids_consultados = [llamada.kwargs.get("pk")
                           for llamada in archivos.using.return_value.filter.call_args_list]
        self.assertEqual(ids_consultados, [archivo_cerrado, archivo_pendiente])
        self.assertNotIn(archivo_nuevo, ids_consultados)
        purga_comun.return_value.purgar.assert_called_once_with(
            solicitante_id=repo.actor, organizacion_id=repo.org,
            archivo_id=archivo_pendiente, crear_cliente=crear_cliente,
            operacion_lote_id=str(operacion))
        self.assertEqual(auditoria.using.return_value.create.call_args.kwargs["accion"],
                         "PAPELERA_VACIADO_CERRADO")

    def test_reintento_vaciado_omite_generacion_reemplazada_y_conserva_pendiente(self):
        repo = RepoFalso()
        operacion, archivo_id = uuid4(), uuid4()
        seleccion = {"version": 1, "operacion_id": str(operacion),
                     "tipo_elemento": "vaciado", "miembros": [
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_id),
                          "generacion_id": "gen-antigua", "fecha_papelera": AHORA.isoformat()},
                     ]}
        evento = SimpleNamespace(detalles=seleccion)
        archivo = SimpleNamespace(pk=archivo_id, organizacion_id=repo.org,
                                  en_papelera=True, fecha_papelera=AHORA)
        repo.ultimo_evento.return_value = SimpleNamespace(
            detalles={"generacion_id": "gen-nueva"})
        auditoria, archivos = MagicMock(), MagicMock()
        cerrada = MagicMock()
        cerrada.exists.return_value = False

        def buscar_eventos(**filtros):
            if filtros.get("accion") == "PAPELERA_VACIADO_INICIADO":
                return SimpleNamespace(first=lambda: evento)
            if filtros.get("accion") == "PAPELERA_VACIADO_CERRADO":
                return cerrada
            return MagicMock()

        auditoria.using.return_value.filter.side_effect = buscar_eventos
        archivos.using.return_value.filter.return_value.first.return_value = archivo
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)

        with patch.object(LogAuditoria, "objects", auditoria), \
             patch.object(Archivo, "objects", archivos), \
             patch("storage.papelera.ServicioPapelera") as purga_comun:
            with self.assertRaises(ErrorPapelera) as error:
                servicio.vaciar(solicitante_id=repo.actor, organizacion_id=repo.org,
                                operacion_id=operacion, crear_cliente=MagicMock())

        self.assertEqual(error.exception.status_code, 503)
        purga_comun.return_value.purgar.assert_not_called()
        auditoria.using.return_value.create.assert_not_called()

    def test_purga_carpeta_con_fallo_fisico_conserva_seleccion_y_contenedor(self):
        repo = RepoFalso()
        raiz_id, archivo_id = uuid4(), uuid4()
        operacion = str(uuid4())
        archivo = SimpleNamespace(pk=archivo_id, organizacion_id=repo.org,
                                  en_papelera=True, fecha_papelera=AHORA)
        raiz = SimpleNamespace(pk=raiz_id, delete=MagicMock())
        seleccion = {"version": 1, "operacion_id": operacion,
                     "raiz_id": str(raiz_id), "miembros": [
                         {"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
                          "generacion_id": "gen-raiz", "manifiesto_operacion_id": "envio-1",
                          "fecha_papelera": AHORA.isoformat()},
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_id),
                          "generacion_id": "gen-archivo", "fecha_papelera": AHORA.isoformat()},
                     ]}
        repo.ultimo_evento.return_value = SimpleNamespace(
            detalles={"generacion_id": "gen-archivo"})
        auditoria, archivos = MagicMock(), MagicMock()
        solicitud = SimpleNamespace(detalles=seleccion)
        auditoria.using.return_value.filter.return_value.order_by.return_value.first.return_value = solicitud
        auditoria.using.return_value.filter.return_value.exists.return_value = False
        archivos.using.return_value.filter.return_value.first.return_value = archivo
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        cliente = MagicMock()

        with patch.object(LogAuditoria, "objects", auditoria), \
             patch.object(Archivo, "objects", archivos), \
             patch.object(Carpeta, "objects") as carpetas, \
             patch("storage.papelera.ServicioPapelera") as purga_comun:
            purga_comun.return_value.purgar.side_effect = ErrorPapelera()
            with self.assertRaises(ErrorPapelera) as error:
                servicio.purgar(solicitante_id=repo.actor, organizacion_id=repo.org,
                                carpeta_id=raiz_id, crear_cliente=cliente)

        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(seleccion["miembros"][0]["recurso_id"], str(raiz.pk))
        raiz.delete.assert_not_called()
        carpetas.using.assert_not_called()
        purga_comun.return_value.purgar.assert_called_once_with(
            solicitante_id=repo.actor, organizacion_id=repo.org,
            archivo_id=archivo_id, crear_cliente=cliente,
            operacion_lote_id=operacion)

    def test_reintento_purga_carpeta_reconoce_archivo_cerrado_y_retira_hoja(self):
        repo = RepoFalso()
        raiz_id, archivo_cerrado, archivo_pendiente = uuid4(), uuid4(), uuid4()
        operacion, envio = str(uuid4()), str(uuid4())
        raiz = SimpleNamespace(pk=raiz_id, organizacion_id=repo.org,
                               padre_id=None, en_papelera=True,
                               fecha_papelera=AHORA, delete=MagicMock())
        archivo = SimpleNamespace(pk=archivo_pendiente, organizacion_id=repo.org,
                                  en_papelera=True, fecha_papelera=AHORA)
        seleccion = {"version": 1, "operacion_id": operacion,
                     "raiz_id": str(raiz_id), "miembros": [
                         {"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
                          "generacion_id": "gen-raiz", "manifiesto_operacion_id": envio,
                          "fecha_papelera": AHORA.isoformat()},
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_cerrado),
                          "generacion_id": "gen-a", "fecha_papelera": AHORA.isoformat()},
                         {"tipo_elemento": "archivo", "recurso_id": str(archivo_pendiente),
                          "generacion_id": "gen-b", "fecha_papelera": AHORA.isoformat()},
                     ]}
        manifiesto = {"version": 1, "cerrado": True, "operacion_id": envio,
                      "raiz_id": str(raiz_id), "raiz_generacion_id": "gen-raiz",
                      "fecha_papelera": AHORA.isoformat(), "miembros": [
                          {"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
                           "generacion_id": "gen-raiz"},
                      ]}
        repo.ultimo_evento.return_value = SimpleNamespace(
            detalles={"generacion_id": "gen-b"})
        auditoria, carpetas, archivos = MagicMock(), MagicMock(), MagicMock()
        solicitud = SimpleNamespace(detalles=seleccion)
        evento_envio = SimpleNamespace(detalles=manifiesto)
        no_cerrado, archivo_a_purgado = MagicMock(), MagicMock()
        no_cerrado.exists.return_value = False
        archivo_a_purgado.exists.return_value = True

        def buscar_eventos(**filtros):
            accion = filtros.get("accion")
            if accion == "PAPELERA_CARPETA_PURGA_SOLICITADA":
                return SimpleNamespace(order_by=lambda *_: SimpleNamespace(first=lambda: solicitud))
            if accion == "PAPELERA_CARPETA_PURGADA":
                return no_cerrado
            if accion == "PAPELERA_PURGADO":
                return archivo_a_purgado
            if accion == "PAPELERA_CARPETA_ENVIADA":
                return SimpleNamespace(order_by=lambda *_: SimpleNamespace(first=lambda: evento_envio))
            return MagicMock()

        auditoria.using.return_value.filter.side_effect = buscar_eventos
        carpetas.using.return_value.filter.return_value.first.return_value = raiz
        carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.return_value = raiz
        archivos.using.return_value.filter.return_value.first.side_effect = [None, archivo]
        archivos.using.return_value.filter.return_value.exists.return_value = False
        carpetas.using.return_value.filter.return_value.exists.return_value = False
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)
        cliente = MagicMock()

        with patch.object(LogAuditoria, "objects", auditoria), \
             patch.object(Carpeta, "objects", carpetas), \
             patch.object(Archivo, "objects", archivos), \
             patch("storage.papelera.ServicioPapelera") as purga_comun:
            resultado = servicio.purgar(solicitante_id=repo.actor,
                                        organizacion_id=repo.org,
                                        carpeta_id=raiz_id, crear_cliente=cliente)

        self.assertIsNone(resultado)
        self.assertEqual(purga_comun.return_value.purgar.call_count, 1)
        purga_comun.return_value.purgar.assert_called_once_with(
            solicitante_id=repo.actor, organizacion_id=repo.org,
            archivo_id=archivo_pendiente, crear_cliente=cliente,
            operacion_lote_id=operacion)
        raiz.delete.assert_called_once_with(using="default")
        self.assertEqual(auditoria.using.return_value.create.call_args.kwargs["accion"],
                         "PAPELERA_CARPETA_PURGADA")

    def test_descendiente_detecta_ciclos_en_vez_de_recorrer_indefinidamente(self):
        desconocido, primero, segundo = uuid4(), uuid4(), uuid4()
        item = SimpleNamespace(pk=uuid4(), padre_id=primero)
        carpetas = {
            primero: SimpleNamespace(pk=primero, padre_id=segundo),
            segundo: SimpleNamespace(pk=segundo, padre_id=primero),
        }
        with self.assertRaises(ErrorPapelera):
            ServicioLotesCarpeta._es_descendiente(item, SimpleNamespace(pk=desconocido), carpetas)

    def test_restauracion_rechaza_manifiesto_o_generacion_de_carpeta_obsoletos(self):
        evento = SimpleNamespace(pk=1)
        nuevo_evento = SimpleNamespace(pk=2)
        datos = {"operacion_id": "lote-1", "raiz_generacion_id": "gen-1"}
        datos_nuevos = {"operacion_id": "lote-2", "raiz_generacion_id": "gen-2"}
        self.assertTrue(ServicioLotesCarpeta._manifiesto_sigue_vigente(
            (evento, datos), (evento, dict(datos))))
        self.assertFalse(ServicioLotesCarpeta._manifiesto_sigue_vigente(
            (evento, datos), (nuevo_evento, datos_nuevos)))

        miembro = {"recurso_id": str(uuid4()), "generacion_id": "gen-1"}
        evento_actual = {"operacion_id": "lote-1", "miembros": [
            {"tipo_elemento": "carpeta", **miembro},
        ]}
        self.assertTrue(ServicioLotesCarpeta._generacion_carpeta_vigente(
            "lote-1", miembro, evento_actual))
        evento_actual["miembros"][0]["generacion_id"] = "gen-2"
        self.assertFalse(ServicioLotesCarpeta._generacion_carpeta_vigente(
            "lote-1", miembro, evento_actual))

    def test_restauracion_bloquea_si_una_carpeta_hija_tiene_purga_pendiente(self):
        repo = RepoFalso()
        raiz_id, hija_id = uuid4(), uuid4()
        fecha = AHORA
        raiz = SimpleNamespace(pk=raiz_id, organizacion_id=repo.org,
                               padre_id=None, nombre="Proyecto", en_papelera=True,
                               fecha_papelera=fecha, save=MagicMock())
        hija = SimpleNamespace(pk=hija_id, organizacion_id=repo.org,
                               padre_id=raiz_id, nombre="Datos", en_papelera=True,
                               fecha_papelera=fecha, save=MagicMock())
        manifiesto = {"version": 1, "operacion_id": "op-1",
                      "raiz_id": str(raiz_id),
                      "raiz_generacion_id": "gen-raiz",
                      "miembros": [
                          {"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
                           "generacion_id": "gen-raiz", "padre_id": None,
                           "nombre": "Proyecto"},
                          {"tipo_elemento": "carpeta", "recurso_id": str(hija_id),
                           "generacion_id": "gen-hija", "padre_id": str(raiz_id),
                           "nombre": "Datos"},
                      ]}
        evento = SimpleNamespace(pk=1)
        repo.lote_purga_pendiente.side_effect = [False, True]
        manager = MagicMock()
        manager.using.return_value.select_for_update.return_value.filter.return_value.first.side_effect = [
            raiz, hija]
        servicio = ServicioLotesCarpeta(repo=repo, reloj=lambda: AHORA)

        with patch.object(servicio, "_manifiesto", return_value=(evento, manifiesto)), \
             patch.object(Carpeta, "objects", manager), \
             self.assertRaises(ErrorPapelera) as error:
            servicio.restaurar(solicitante_id=repo.actor, organizacion_id=repo.org,
                               carpeta_id=raiz_id)

        self.assertEqual(error.exception.status_code, 409)
        raiz.save.assert_not_called()
        hija.save.assert_not_called()

    def test_restauracion_lote_completa_en_capacidad_exacta_y_conserva_el_previo(self):
        resultado = self._restaurar_lote(capacidad=(100, 60, 15))

        self.assertFalse(resultado.raiz.en_papelera)
        self.assertFalse(resultado.archivo.en_papelera)
        self.assertEqual(resultado.archivo.carpeta_id, resultado.raiz.pk)
        self.assertEqual(resultado.independiente.fecha_papelera,
                         datetime(2026, 10, 20, 9, tzinfo=timezone.utc))
        resultado.independiente.save.assert_not_called()
        ids_releidos = [llamada.kwargs["pk"] for llamada in
                        resultado.archivos.using.return_value.select_for_update.return_value.filter.call_args_list]
        self.assertEqual(ids_releidos, [resultado.archivo.pk])
        self.assertNotIn(resultado.independiente.pk, ids_releidos)
        resultado.repo.evento_restauracion.assert_called_once_with(
            resultado.archivo, resultado.repo.actor, "gen-archivo")
        self.assertEqual(resultado.auditoria.using.return_value.create.call_args.kwargs["accion"],
                         "PAPELERA_CARPETA_RESTAURADA")

    def test_restauracion_lote_no_mueve_un_miembro_ya_restaurado_aparte(self):
        resultado = self._restaurar_lote(miembro_restaurado_aparte=True)

        self.assertFalse(resultado.archivo.en_papelera)
        self.assertFalse(resultado.restaurado_aparte.en_papelera)
        resultado.restaurado_aparte.save.assert_not_called()
        self.assertEqual(resultado.repo.evento_restauracion.call_count, 1)

    def test_restauracion_nivel_tres_rechaza_destino_sin_acl_sin_mutar(self):
        resultado = self._restaurar_lote(
            nivel=3, padre_raiz=True, permiso_destino=False)

        self.assertIsInstance(resultado.error, PermissionDenied)
        resultado.raiz.save.assert_not_called()
        resultado.archivo.save.assert_not_called()
        resultado.repo.evento_restauracion.assert_not_called()
        resultado.auditoria.using.return_value.create.assert_not_called()

    def test_restauracion_lote_rechaza_cuota_y_colision_antes_de_mutar(self):
        for capacidad, colision, codigo in (
                ((100, 60, 16), False, "CUOTA_EXCEDIDA"),
                ((100, 0, 0), True, "VALIDATION_ERROR")):
            with self.subTest(capacidad=capacidad, colision=colision):
                resultado = self._restaurar_lote(capacidad=capacidad, colision=colision)
                self.assertIsNotNone(resultado.error)
                self.assertEqual(resultado.error.codigo, codigo)
                resultado.raiz.save.assert_not_called()
                resultado.archivo.save.assert_not_called()
                resultado.repo.evento_restauracion.assert_not_called()

    def test_fallo_de_auditoria_restaura_estado_de_todo_el_lote(self):
        resultado = self._restaurar_lote(fallo_auditoria=True)

        self.assertIsNotNone(resultado.error)
        self.assertEqual(resultado.error.status_code, 503)
        self.assertTrue(resultado.raiz.en_papelera)
        self.assertTrue(resultado.archivo.en_papelera)
        self.assertEqual(resultado.archivo.carpeta_id, resultado.raiz.pk)

    def test_seleccion_fija_rechaza_miembros_corruptos_o_duplicados(self):
        miembro = {"tipo_elemento": "archivo", "recurso_id": str(uuid4()),
                   "generacion_id": "gen-1", "fecha_papelera": AHORA.isoformat()}
        ServicioLotesCarpeta._validar_miembros_seleccion([miembro])
        with self.assertRaises(ErrorPapelera):
            ServicioLotesCarpeta._validar_miembros_seleccion([miembro, dict(miembro)])
        with self.assertRaises(ErrorPapelera):
            ServicioLotesCarpeta._validar_miembros_seleccion([
                {**miembro, "fecha_papelera": "no-es-fecha"}])
        with self.assertRaises(ErrorPapelera):
            ServicioLotesCarpeta._validar_miembros_seleccion([
                {"tipo_elemento": "carpeta", "recurso_id": str(uuid4()),
                 "generacion_id": "gen-1", "fecha_papelera": AHORA.isoformat()}])

    def test_arbol_mayor_a_cien_se_rechaza_con_lectura_acotada(self):
        repo = RepoFalso()
        raiz = SimpleNamespace(pk=uuid4(), organizacion_id=repo.org)
        raiz_qs, hijos_qs = MagicMock(), MagicMock()
        raiz_qs.first.return_value = raiz
        hijos_qs.order_by.return_value.__getitem__.return_value = [
            SimpleNamespace(pk=uuid4(), organizacion_id=repo.org) for _ in range(101)
        ]
        manager = MagicMock()
        manager.using.return_value.filter.side_effect = [raiz_qs, hijos_qs]
        servicio = ServicioLotesCarpeta(repo=repo)
        with patch("storage.lotes_papelera.Carpeta.objects", manager), \
             self.assertRaises(ErrorPapelera) as error:
            servicio._arbol(raiz.pk, repo.org)
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("limite", error.exception.detail["error"]["fields"])

    def test_arbol_de_cien_elementos_se_acepta_sin_superar_lecturas_acotadas(self):
        repo = RepoFalso()
        raiz_id = uuid4()
        raiz = SimpleNamespace(pk=raiz_id, organizacion_id=repo.org)
        hijos = [SimpleNamespace(pk=uuid4(), organizacion_id=repo.org,
                                 padre_id=raiz_id) for _ in range(99)]
        raices_qs, hijos_qs, hojas_qs = MagicMock(), MagicMock(), MagicMock()
        raices_qs.first.return_value = raiz
        hijos_qs.order_by.return_value.__getitem__.return_value = hijos
        hojas_qs.order_by.return_value.__getitem__.return_value = []
        carpetas, archivos = MagicMock(), MagicMock()
        carpetas.using.return_value.filter.side_effect = [raices_qs, hijos_qs, hojas_qs]
        archivos.using.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = []
        servicio = ServicioLotesCarpeta(repo=repo)

        with patch("storage.lotes_papelera.Carpeta.objects", carpetas), \
             patch("storage.lotes_papelera.Archivo.objects", archivos):
            resultado_raiz, resultado_carpetas, resultado_archivos = servicio._arbol(
                raiz_id, repo.org)

        self.assertIs(resultado_raiz, raiz)
        self.assertEqual(len(resultado_carpetas), 100)
        self.assertEqual(resultado_archivos, {})

    def test_arbol_multinivel_se_recoge_completo_y_delimitado_a_organizacion(self):
        repo = RepoFalso()
        raiz_id, hija_id, nieta_id = uuid4(), uuid4(), uuid4()
        raiz = SimpleNamespace(pk=raiz_id, organizacion_id=repo.org, padre_id=None)
        hija = SimpleNamespace(pk=hija_id, organizacion_id=repo.org, padre_id=raiz_id)
        nieta = SimpleNamespace(pk=nieta_id, organizacion_id=repo.org, padre_id=hija_id)
        consultas_carpetas = [MagicMock() for _ in range(4)]
        consultas_carpetas[0].first.return_value = raiz
        consultas_carpetas[1].order_by.return_value.__getitem__.return_value = [hija]
        consultas_carpetas[2].order_by.return_value.__getitem__.return_value = [nieta]
        consultas_carpetas[3].order_by.return_value.__getitem__.return_value = []
        consultas_archivos = [MagicMock() for _ in range(3)]
        for consulta in consultas_archivos:
            consulta.order_by.return_value.__getitem__.return_value = []
        manager_carpetas, manager_archivos = MagicMock(), MagicMock()
        manager_carpetas.using.return_value.filter.side_effect = consultas_carpetas
        manager_archivos.using.return_value.filter.side_effect = consultas_archivos
        servicio = ServicioLotesCarpeta(repo=repo)

        with patch("storage.lotes_papelera.Carpeta.objects", manager_carpetas), \
             patch("storage.lotes_papelera.Archivo.objects", manager_archivos):
            _, carpetas, archivos = servicio._arbol(raiz_id, repo.org)

        self.assertEqual(set(carpetas), {raiz_id, hija_id, nieta_id})
        self.assertEqual(archivos, {})

    def test_arbol_rechaza_descendiente_de_otra_organizacion(self):
        repo = RepoFalso()
        raiz_id = uuid4()
        raiz = SimpleNamespace(pk=raiz_id, organizacion_id=repo.org, padre_id=None)
        hija = SimpleNamespace(pk=uuid4(), organizacion_id=uuid4(), padre_id=raiz_id)
        consultas = [MagicMock(), MagicMock()]
        consultas[0].first.return_value = raiz
        consultas[1].order_by.return_value.__getitem__.return_value = [hija]
        carpetas = MagicMock()
        carpetas.using.return_value.filter.side_effect = consultas
        servicio = ServicioLotesCarpeta(repo=repo)

        with patch("storage.lotes_papelera.Carpeta.objects", carpetas), \
             self.assertRaises(ErrorPapelera):
            servicio._arbol(raiz_id, repo.org)

    def _configurar_purga_contenedor(self, *, tiene_archivo):
        repo = RepositorioPapelera()
        raiz_id, org = uuid4(), uuid4()
        carpeta = Carpeta(pk=raiz_id, organizacion_id=org, padre_id=None,
                          nombre="Proyecto", en_papelera=True, fecha_papelera=AHORA)
        carpeta.delete = MagicMock()
        carpetas, archivos, auditoria = MagicMock(), MagicMock(), MagicMock()
        consulta_carpetas = carpetas.using.return_value.filter.return_value
        consulta_carpetas.first.return_value = carpeta
        consulta_carpetas.exists.return_value = False
        carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.return_value = carpeta
        consulta_carpetas.annotate.return_value.filter.return_value.filter.return_value.order_by.return_value.values_list.return_value = [
            (raiz_id, org, AHORA)]
        consulta_archivos = archivos.using.return_value.filter.return_value
        consulta_archivos.exists.return_value = tiene_archivo
        manifiesto = {"version": 1, "cerrado": True, "operacion_id": "envio-1",
                      "raiz_id": str(raiz_id), "fecha_papelera": AHORA.isoformat(),
                      "miembros": [{"tipo_elemento": "carpeta", "recurso_id": str(raiz_id),
                                    "generacion_id": "gen-raiz"}]}
        auditoria.using.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            detalles=manifiesto)
        return repo, org, carpeta, carpetas, archivos, auditoria

    def test_purga_automatica_conserva_contenedor_si_sigue_teniendo_archivo(self):
        repo, org, carpeta, carpetas, archivos, auditoria = self._configurar_purga_contenedor(
            tiene_archivo=True)
        with patch.object(repo, "transaccion", return_value=nullcontext()), \
             patch.object(repo, "lote_purga_pendiente", return_value=False), \
             patch.object(Carpeta, "objects", carpetas), \
             patch.object(Archivo, "objects", archivos), \
             patch.object(LogAuditoria, "objects", auditoria):
            purgadas = repo.purgar_carpetas_vacias_vencidas(
                corte=AHORA, limite=1, organizacion_id=org)

        self.assertEqual(purgadas, 0)
        carpeta.delete.assert_not_called()
        auditoria.using.return_value.create.assert_not_called()

    def test_purga_automatica_retira_y_audita_contenedor_vacio_vencido(self):
        repo, org, carpeta, carpetas, archivos, auditoria = self._configurar_purga_contenedor(
            tiene_archivo=False)
        with patch.object(repo, "transaccion", return_value=nullcontext()), \
             patch.object(repo, "lote_purga_pendiente", return_value=False), \
             patch.object(Carpeta, "objects", carpetas), \
             patch.object(Archivo, "objects", archivos), \
             patch.object(LogAuditoria, "objects", auditoria):
            purgadas = repo.purgar_carpetas_vacias_vencidas(
                corte=AHORA, limite=1, organizacion_id=org)

        self.assertEqual(purgadas, 1)
        carpeta.delete.assert_called_once_with(using="default")
        llamada = auditoria.using.return_value.create.call_args.kwargs
        self.assertEqual(llamada["accion"], "PAPELERA_CARPETA_RECURSO_PURGADO")
        self.assertEqual(llamada["detalles"]["fecha_papelera"], AHORA.isoformat())

    def test_purga_automatica_no_retira_contenedor_con_lote_pendiente(self):
        repo, org, carpeta, carpetas, archivos, auditoria = self._configurar_purga_contenedor(
            tiene_archivo=False)
        with patch.object(repo, "transaccion", return_value=nullcontext()), \
             patch.object(repo, "lote_purga_pendiente", return_value=True), \
             patch.object(Carpeta, "objects", carpetas), \
             patch.object(Archivo, "objects", archivos), \
             patch.object(LogAuditoria, "objects", auditoria):
            purgadas = repo.purgar_carpetas_vacias_vencidas(
                corte=AHORA, limite=1, organizacion_id=org)

        self.assertEqual(purgadas, 0)
        carpeta.delete.assert_not_called()
        auditoria.using.return_value.create.assert_not_called()
