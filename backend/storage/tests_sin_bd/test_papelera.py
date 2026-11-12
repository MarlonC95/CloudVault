from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory, force_authenticate

from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from common.ambito import Ambito
from storage.papelera import ErrorPapelera, ServicioPapelera
from storage.permisos_papelera import autorizar_envio
from storage.repositorio_papelera import RepositorioPapelera
from storage.views import ArchivoViewSet, PapeleraViewSet

AHORA = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


class RepositorioFalso:
    def __init__(self):
        self.actor, self.org, self.id = uuid4(), uuid4(), uuid4()
        self.fila = SimpleNamespace(pk=self.id, organizacion_id=self.org,
                                   carpeta_id=uuid4(), nombre="informe.pdf", clave_s3="objeto",
                                   tamano_bytes=200, en_papelera=False, fecha_papelera=None)
        self.rol, self.grants = 0, []
        self.eventos, self.pasos = [], []
        self.pendiente = self.falla_auditoria = self.falla_commit = self.falla_lock = False
        self.intencion = None
        self.consultas_lote = []
        self.deleted = False
        self.en_transaccion = False
        self.falla_cierre = False
        self.falla_commit_en = None
        self.commits_intentados = 0

    @contextmanager
    def reclamar(self, archivo_id):
        self.pasos.append("reclamo")
        if self.falla_lock:
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        def comprobar():
            self.pasos.append("comprobar")
            if self.falla_lock:
                raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        yield comprobar
        self.pasos.append("liberar")

    @contextmanager
    def transaccion(self, org):
        self.pasos.append("cuota")
        anterior, eventos, intencion, deleted = (deepcopy(self.fila), deepcopy(self.eventos),
                                                  deepcopy(self.intencion), self.deleted)
        self.en_transaccion = True
        try:
            yield
            self.commits_intentados += 1
            if self.falla_commit:
                raise OperationalError("synthetic-commit")
            if self.falla_commit_en == self.commits_intentados:
                raise OperationalError("synthetic-commit")
            self.pasos.append("commit")
        except Exception:
            self.fila, self.eventos, self.intencion, self.deleted = anterior, eventos, intencion, deleted
            self.pasos.append("rollback")
            raise
        finally:
            self.en_transaccion = False

    def nivel(self, actor, org):
        self.pasos.append("membresia")
        if actor != self.actor or org != self.org:
            raise NotFound()
        return self.rol

    def archivo(self, archivo_id, org):
        self.pasos.append("relectura")
        return self.fila if archivo_id == self.id and org == self.org and not self.deleted else None

    def permisos(self, actor, archivo):
        return self.grants

    def purga_pendiente(self, archivo):
        return self.pendiente

    def lote_purga_pendiente(self, organizacion_id, recurso_id, *, excluir_operacion=None):
        self.consultas_lote.append((organizacion_id, recurso_id, excluir_operacion))
        return False

    def generar_o_reutilizar_intencion(self, archivo, actor, origen="MANUAL"):
        self.pasos.append("intencion")
        if self.intencion is None:
            generacion = str(uuid4())
            self.intencion = {"version":1, "operacion_id":str(uuid4()),
                              "generacion_id":generacion, "tipo_elemento":"archivo",
                              "recurso_id":str(archivo.pk), "fecha_papelera":AHORA.isoformat(),
                              "origen":origen, "clave_s3":archivo.clave_s3, "intento":0}
            self.eventos.append(self.intencion.copy())
        return self.intencion

    def referencia_incompatible(self, archivo, clave):
        return False

    def cerrar_purga(self, archivo, actor, intencion, *, bytes_fisicos_purgados=0):
        self.pasos.append("cierre")
        if self.falla_cierre:
            raise OperationalError("synthetic-close")
        self.eventos.append({"accion":"PAPELERA_PURGADO", "operacion_id":intencion["operacion_id"],
                             "generacion_id":intencion["generacion_id"]})
        self.deleted = True

    def auditar_reintento_purga(self, archivo, actor, intencion, motivo, *, ahora=None,
                                bytes_fisicos_confirmados=0):
        self.pasos.append("reintento")
        self.eventos.append({**intencion, "intento":1, "motivo":motivo})

    def marcar(self, archivo, ahora):
        self.pasos.append("marcar")
        archivo.en_papelera, archivo.fecha_papelera = True, ahora

    def auditar(self, **evento):
        self.pasos.append("auditar")
        if self.falla_auditoria:
            raise OperationalError("synthetic-secret")
        self.eventos.append(evento["detalles"])

    def ultimo_evento(self, archivo):
        return self.ultimo if hasattr(self, 'ultimo') else None

    def destino(self, archivo, actor, nivel):
        return self.destino_id if hasattr(self, 'destino_id') else archivo.carpeta_id

    def nombre_disponible(self, *args, **kwargs):
        return not getattr(self, 'colision', False)

    def capacidad(self, org, ahora):
        return getattr(self, 'cuota', (1000, 100, 100))

    def reactivar(self, archivo, destino):
        archivo.carpeta_id, archivo.en_papelera, archivo.fecha_papelera = destino, False, None

    def evento_restauracion(self, archivo, actor, generacion, accion='PAPELERA_RESTAURADO'):
        if self.falla_auditoria: raise OperationalError('synthetic')
        self.ultimo = SimpleNamespace(accion=accion, detalles={'generacion_id':generacion})
        self.eventos.append({'accion':accion, 'generacion_id':generacion})


class BasePapeleraTests(SimpleTestCase):
    def setUp(self):
        self.repo = RepositorioFalso()
        self.servicio = ServicioPapelera(repositorio=self.repo, reloj=lambda: AHORA)
        self.datos = dict(solicitante_id=self.repo.actor, organizacion_id=self.repo.org,
                          archivo_id=self.repo.id)


class EnvioPapeleraTests(BasePapeleraTests):
    def test_envio_conserva_metadatos_y_audita_antes_del_commit(self):
        anterior = vars(self.repo.fila).copy()
        self.servicio.enviar(**self.datos)
        self.assertTrue(self.repo.fila.en_papelera)
        self.assertEqual(self.repo.fila.fecha_papelera, AHORA)
        for key in ['pk', 'organizacion_id', 'carpeta_id', 'nombre', 'clave_s3', 'tamano_bytes']:
            self.assertEqual(getattr(self.repo.fila, key), anterior[key])
        self.assertLess(self.repo.pasos.index('reclamo'), self.repo.pasos.index('cuota'))
        self.assertLess(self.repo.pasos.index('auditar'), self.repo.pasos.index('commit'))
        self.assertEqual(len(self.repo.eventos), 1)
        evento = self.repo.eventos[0]
        self.assertEqual(evento['version'], 1)
        self.assertEqual(evento['recurso_id'], str(self.repo.id))
        self.assertNotIn('clave_s3', evento)
        self.assertNotEqual(evento['operacion_id'], evento['generacion_id'])

    def test_repetir_conserva_fecha_y_generacion(self):
        self.servicio.enviar(**self.datos)
        evento = deepcopy(self.repo.eventos)
        self.servicio.enviar(**self.datos)
        self.assertEqual(self.repo.eventos, evento)
        self.assertEqual(self.repo.fila.fecha_papelera, AHORA)
        self.assertEqual(self.repo.pasos.count('marcar'), 1)

    def test_nuevo_envio_tras_restaurar_tiene_otra_generacion(self):
        self.servicio.enviar(**self.datos)
        self.repo.fila.en_papelera = False
        self.repo.fila.fecha_papelera = None
        self.servicio.enviar(**self.datos)
        self.assertNotEqual(self.repo.eventos[0]['generacion_id'], self.repo.eventos[1]['generacion_id'])

    def test_roles_no_permitidos_no_mutan(self):
        for rol in (1, 2, 4):
            with self.subTest(rol=rol):
                self.repo.rol = rol
                with self.assertRaises(PermissionDenied):
                    self.servicio.enviar(**self.datos)
                self.assertFalse(self.repo.fila.en_papelera)
                self.assertEqual(self.repo.eventos, [])

    def test_avanzado_edicion_valida_y_lectura_no_basta(self):
        self.repo.rol = 3
        self.repo.grants = ['read']
        with self.assertRaises(PermissionDenied):
            self.servicio.enviar(**self.datos)
        self.repo.grants = ['write']
        self.servicio.enviar(**self.datos)
        self.assertTrue(self.repo.fila.en_papelera)

    def test_avanzado_sin_acl_no_revela_archivo(self):
        self.repo.rol, self.repo.grants = 3, ['unknown']
        with self.assertRaises(NotFound):
            self.servicio.enviar(**self.datos)

    def test_aislamiento_y_archivo_inexistente(self):
        for campo in ('solicitante_id', 'organizacion_id', 'archivo_id'):
            with self.subTest(campo=campo), self.assertRaises(NotFound):
                self.servicio.enviar(**{**self.datos, campo: uuid4()})
        self.assertEqual(self.repo.eventos, [])

    def test_fallo_auditoria_o_commit_revierte_y_oculta_error(self):
        for atributo in ('falla_auditoria', 'falla_commit'):
            with self.subTest(atributo=atributo):
                self.repo.falla_auditoria = self.repo.falla_commit = False
                setattr(self.repo, atributo, True)
                with self.assertRaises(ErrorPapelera) as error:
                    self.servicio.enviar(**self.datos)
                self.assertEqual(error.exception.status_code, 503)
                self.assertNotIn('synthetic', str(error.exception.detail))
                self.assertFalse(self.repo.fila.en_papelera)
                self.assertEqual(self.repo.eventos, [])

    def test_intencion_pendiente_impide_nuevo_envio_y_repeticion(self):
        self.repo.pendiente = True
        for eliminado in (False, True):
            self.repo.fila.en_papelera = eliminado
            with self.assertRaises(ErrorPapelera) as error:
                self.servicio.enviar(**self.datos)
            self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.repo.eventos, [])

    def test_lock_ocupado_no_modifica(self):
        self.repo.falla_lock = True
        with self.assertRaises(ErrorPapelera):
            self.servicio.enviar(**self.datos)
        self.assertNotIn('marcar', self.repo.pasos)

    def test_perdida_del_reclamo_antes_del_commit_no_confirma(self):
        with patch.object(self.repo, 'reclamar') as reclamar:
            count = 0
            def comprobar():
                nonlocal count
                count += 1
                if count == 2:
                    raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
            @contextmanager
            def guard(*args):
                yield comprobar
            reclamar.side_effect = guard
            with self.assertRaises(ErrorPapelera):
                self.servicio.enviar(**self.datos)
        self.assertFalse(self.repo.fila.en_papelera)
        self.assertEqual(self.repo.eventos, [])

    def test_identificador_invalido_no_abre_transaccion(self):
        with self.assertRaises(ValidationError):
            self.servicio.enviar(**{**self.datos, 'archivo_id': 'incorrecto'})
        self.assertEqual(self.repo.pasos, [])

    def test_mutacion_ordinaria_relee_y_rechaza_eliminado(self):
        self.repo.fila.en_papelera = True
        with self.assertRaises(NotFound):
            with self.servicio.proteger(**self.datos, eliminado=False):
                self.fail('No debe modificar un eliminado')

    def test_constructor_sin_io(self):
        with patch('storage.repositorio_papelera.connections') as conexiones:
            ServicioPapelera()
        conexiones.__getitem__.assert_not_called()


class EndpointEnvioTests(BasePapeleraTests):
    def solicitud(self, datos=None, org=None, pk=None):
        request = APIRequestFactory().delete('/api/v1/archivos/id/', datos or {}, format='json')
        force_authenticate(request, user=SimpleNamespace(pk=self.repo.actor, is_authenticated=True))
        vista = ArchivoViewSet.as_view({'delete': 'destroy'})
        with patch('storage.views.resolver_organizacion', return_value=SimpleNamespace(organizacion_id=org or self.repo.org)), \
             patch('storage.views.ServicioPapelera', return_value=self.servicio), \
             patch('storage.views.ClienteS3', side_effect=AssertionError('Envío no llama a S3')):
            return vista(request, pk=str(pk or self.repo.id))

    def test_delete_respuesta_compatible_y_sin_s3(self):
        response = self.solicitud()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'data': {'mensaje': 'El archivo se movió a la papelera.'}})
        self.assertIn('commit', self.repo.pasos)

    def test_delete_errores_con_sobre_y_sin_datos_tecnicos(self):
        self.repo.rol = 2
        response = self.solicitud()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'SIN_PERMISO')
        self.repo.rol = 0
        self.repo.falla_commit = True
        response = self.solicitud()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'SERVICE_UNAVAILABLE')

    def test_ambitos_contradictorios_se_rechazan(self):
        req = APIRequestFactory().delete('/?organizacion_id='+str(self.repo.org),
                                        {'organizacion_id': str(uuid4())}, format='json')
        force_authenticate(req, user=SimpleNamespace(pk=self.repo.actor, is_authenticated=True))
        response = ArchivoViewSet.as_view({'delete':'destroy'})(req, pk=str(self.repo.id))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.repo.pasos, [])

    def test_no_autenticado_no_llega_al_servicio(self):
        req = APIRequestFactory().delete('/')
        with patch('storage.views.ServicioPapelera') as factory:
            response = ArchivoViewSet.as_view({'delete':'destroy'},
                        authentication_classes=[BasicAuthentication],
                        permission_classes=[IsAuthenticated])(req, pk=str(self.repo.id))
        self.assertEqual(response.status_code, 401)
        factory.assert_not_called()


class AdaptadorTests(SimpleTestCase):
    def test_marcar_solo_guarda_campos_logicos_sin_contador(self):
        archivo = MagicMock()
        RepositorioPapelera().marcar(archivo, AHORA)
        archivo.save.assert_called_once_with(using='default', update_fields=['en_papelera','fecha_papelera','actualizado_en'])
        archivo.delete.assert_not_called()

    def test_alias_permisos_y_concesiones_invalidas(self):
        for grant in ('write','ESCRITURA','admin','ADMINISTRACION'):
            autorizar_envio(3,[grant])
        for grant in ('LECTURA','read'):
            with self.assertRaises(PermissionDenied): autorizar_envio(3,[grant])
        with self.assertRaises(NotFound): autorizar_envio(3,['WRITE',None,123])

class CoordinacionVistasTests(BasePapeleraTests):
    def llamada(self, method, viewset, action, data=None):
        request = getattr(APIRequestFactory(), method)('/', data or {}, format='json')
        force_authenticate(request, user=SimpleNamespace(pk=self.repo.actor, is_authenticated=True))
        with patch('storage.views.resolver_organizacion', return_value=Ambito(self.repo.org, 0)), \
             patch('storage.views.ServicioPapelera', return_value=self.servicio):
            return viewset.as_view({method:action})(request, pk=str(self.repo.id))

    def test_renombrar_y_mover_rechazan_eliminado_releido(self):
        self.repo.fila.en_papelera = True
        for action, data, method in [('partial_update', {'nombre':'nuevo'}, 'patch'),
                                      ('mover', {'carpeta_id':None}, 'post')]:
            with self.subTest(action=action):
                response = self.llamada(method, ArchivoViewSet, action, data)
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.repo.fila.nombre, 'informe.pdf')

    def test_restaurar_comparte_reclamo_y_relectura(self):
        self.repo.fila.en_papelera = True
        self.repo.fila.fecha_papelera = AHORA
        self.repo.fila.carpeta_id = None
        self.repo.fila.save = MagicMock()
        response = self.llamada('post', PapeleraViewSet, 'restaurar')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.repo.fila.en_papelera)
        self.assertEqual(self.repo.pasos[0], 'reclamo')
        self.assertIn('relectura', self.repo.pasos)
        self.assertIn('commit', self.repo.pasos)

    def test_restaurar_intencion_pendiente_no_reactiva(self):
        self.repo.fila.en_papelera = True
        self.repo.pendiente = True
        response = self.llamada('post', PapeleraViewSet, 'restaurar')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(self.repo.fila.en_papelera)

    def test_purga_conserva_reclamo_pero_no_transaccion_durante_s3(self):
        self.repo.fila.en_papelera = True
        def borrar(clave, **kwargs):
            self.assertIn('commit', self.repo.pasos)
            self.assertNotIn('liberar', self.repo.pasos)
            self.assertFalse(self.repo.en_transaccion)
            self.assertEqual(clave, self.repo.fila.clave_s3)
            self.repo.pasos.append('s3')
        with patch('storage.views.ClienteS3') as cliente, \
             patch('storage.views.ConfiguracionS3.desde_entorno', return_value=object()):
            cliente.return_value.borrar_fisico_verificado.side_effect = borrar
            response = self.llamada('delete', PapeleraViewSet, 'destroy')
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.repo.deleted)
        self.assertLess(self.repo.pasos.index('intencion'), self.repo.pasos.index('s3'))
        self.assertLess(self.repo.pasos.index('s3'), self.repo.pasos.index('cierre'))
        self.assertEqual(self.repo.pasos.count('commit'), 2)
        self.assertEqual(self.repo.pasos[-1], 'liberar')
        cliente.return_value.cerrar.assert_called_once()

    def test_vista_autoriza_antes_de_crear_cliente_s3(self):
        self.repo.rol = 3
        with patch('storage.views.ClienteS3') as cliente:
            response = self.llamada('delete', PapeleraViewSet, 'destroy')
        self.assertEqual(response.status_code, 403)
        cliente.assert_not_called()


class PurgaFaseTresTests(BasePapeleraTests):
    def setUp(self):
        super().setUp()
        self.repo.fila.en_papelera = True
        self.repo.fila.fecha_papelera = AHORA
        self.cliente = MagicMock()

    def purgar(self):
        return self.servicio.purgar(**self.datos, cliente=self.cliente)

    def test_rol_no_autorizado_y_archivo_activo_no_alcanzan_s3(self):
        self.repo.rol = 3
        with self.assertRaises(PermissionDenied):
            self.purgar()
        self.cliente.borrar_fisico_verificado.assert_not_called()
        self.repo.rol = 0
        self.repo.fila.en_papelera = False
        with self.assertRaises(ErrorPapelera) as error:
            self.purgar()
        self.assertEqual(error.exception.status_code, 409)
        self.cliente.borrar_fisico_verificado.assert_not_called()

    def test_intencion_commit_precede_s3_y_cierre(self):
        self.cliente.borrar_fisico_verificado.side_effect = lambda clave: (
            self.assertFalse(self.repo.en_transaccion),
            self.assertIn('commit', self.repo.pasos),
            self.repo.pasos.append('s3'))
        self.purgar()
        self.assertLess(self.repo.pasos.index('intencion'), self.repo.pasos.index('commit'))
        self.assertLess(self.repo.pasos.index('commit'), self.repo.pasos.index('s3'))
        self.assertLess(self.repo.pasos.index('s3'), self.repo.pasos.index('cierre'))
        self.assertTrue(self.repo.deleted)

    def test_purga_de_lote_reenvia_su_id_para_conservar_el_bloqueo_a_terceros(self):
        operacion = str(uuid4())
        self.servicio.purgar(**self.datos, cliente=self.cliente,
                             operacion_lote_id=operacion)
        self.assertEqual(self.repo.consultas_lote,
                         [(self.repo.org, self.repo.id, operacion)])
        self.assertTrue(self.repo.deleted)

    def test_fallo_al_confirmar_intencion_no_toca_s3(self):
        self.repo.falla_commit = True
        with self.assertRaises(ErrorPapelera):
            self.purgar()
        self.cliente.borrar_fisico_verificado.assert_not_called()
        self.assertFalse(self.repo.deleted)

    def test_fallo_s3_conserva_operacion_y_reintenta_la_misma(self):
        self.cliente.borrar_fisico_verificado.side_effect = [RuntimeError('timeout'), None]
        with self.assertRaises(ErrorPapelera):
            self.purgar()
        op_id = self.repo.intencion['operacion_id']
        self.assertTrue(any(e.get('motivo') == 'AUSENCIA_NO_CONFIRMADA' for e in self.repo.eventos))
        servicio_recuperado = ServicioPapelera(repositorio=self.repo, reloj=lambda: AHORA)
        servicio_recuperado.purgar(**self.datos, cliente=self.cliente)
        self.assertEqual(self.repo.intencion['operacion_id'], op_id)
        self.assertEqual(self.cliente.borrar_fisico_verificado.call_count, 2)
        self.assertTrue(self.repo.deleted)

    def test_fallo_de_cierre_no_devuelve_exito_y_deja_pendiente(self):
        self.repo.falla_cierre = True
        with self.assertRaises(ErrorPapelera):
            self.purgar()
        self.assertFalse(self.repo.deleted)
        self.assertTrue(any(e.get('motivo') == 'CIERRE' for e in self.repo.eventos))
        self.repo.falla_cierre = False
        self.purgar()
        self.assertTrue(self.repo.deleted)

    def test_fallo_del_commit_final_mantiene_intencion_y_no_devuelve_204(self):
        self.repo.falla_commit_en = 2
        with self.assertRaises(ErrorPapelera):
            self.purgar()
        self.assertEqual(self.repo.commits_intentados, 3)
        self.assertFalse(self.repo.deleted)
        self.assertTrue(any(e.get('motivo') == 'CIERRE' for e in self.repo.eventos))

    def test_perdida_de_reclamo_durante_s3_no_cierra_la_intencion(self):
        def borrar(_clave):
            self.repo.falla_lock = True
        self.cliente.borrar_fisico_verificado.side_effect = borrar
        with self.assertRaises(ErrorPapelera):
            self.servicio.purgar(**self.datos, crear_cliente=lambda: self.cliente)
        self.assertFalse(self.repo.deleted)
        self.assertTrue(any(e.get('motivo') == 'AUSENCIA_NO_CONFIRMADA' for e in self.repo.eventos))
        self.cliente.cerrar.assert_called_once()

    def test_listado_propietario_conserva_filtro_de_ambito(self):
        vista = PapeleraViewSet()
        with patch.object(vista, '_ambito', return_value=Ambito(self.repo.org, 0)), \
             patch('storage.views.Archivo.objects') as archivos:
            vista.get_queryset()
        archivos.filter.assert_called_once_with(organizacion_id=self.repo.org, en_papelera=True)

class ContratosInvalidosTests(BasePapeleraTests):
    def test_cuerpos_no_objeto_son_400_sin_io(self):
        for payload in ([], ['x'], 123, 'texto', None):
            for method, cls, action in [('delete', ArchivoViewSet, 'destroy'),
                                         ('patch', ArchivoViewSet, 'partial_update'),
                                         ('post', ArchivoViewSet, 'mover')]:
                with self.subTest(payload=payload, action=action):
                    import json
                    req = APIRequestFactory().generic(method.upper(), '/', json.dumps(payload),
                                                       content_type='application/json')
                    force_authenticate(req, user=SimpleNamespace(pk=self.repo.actor, is_authenticated=True))
                    with patch('storage.views.resolver_organizacion') as resolver:
                        response = cls.as_view({method:action})(req, pk=str(self.repo.id))
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
                    resolver.assert_not_called()


class ReglasAdaptadorTests(SimpleTestCase):
    def setUp(self):
        self.repo = RepositorioPapelera()
        self.actor, self.org = uuid4(), uuid4()
        self.padre, self.abuelo = uuid4(), uuid4()
        self.archivo = SimpleNamespace(pk=uuid4(), organizacion_id=self.org, carpeta_id=self.padre)

    def test_acl_heredada_recorre_solo_ancestros_del_ambito(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [('write',)]
        with patch('storage.repositorio_papelera.Carpeta.objects') as carpetas, \
             patch('storage.repositorio_papelera.connections') as conexiones:
            conexiones.__getitem__.return_value.cursor.return_value.__enter__.return_value = cursor
            lookup = carpetas.using.return_value.select_for_update.return_value.filter
            lookup.return_value.first.side_effect = [SimpleNamespace(padre_id=self.abuelo), SimpleNamespace(padre_id=None)]
            self.assertEqual(self.repo.permisos(self.actor, self.archivo), ['write'])
            self.assertEqual(lookup.call_count, 2)
            for call in lookup.call_args_list:
                self.assertEqual(call.kwargs['organizacion_id'], self.org)
        self.assertEqual(cursor.execute.call_args.args[1], [self.actor,self.archivo.pk,[self.padre,self.abuelo]])

    def test_ciclo_o_ancestro_ajeno_no_concede_acceso(self):
        for valor in (None, SimpleNamespace(padre_id=self.padre)):
            with self.subTest(valor=valor), patch('storage.repositorio_papelera.Carpeta.objects') as carpetas:
                carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.return_value = valor
                with self.assertRaises(ErrorPapelera):
                    self.repo.permisos(self.actor, self.archivo)

    def test_intencion_requiere_cierre_de_misma_operacion_y_generacion(self):
        solicitud = SimpleNamespace(detalles={'version':1,'operacion_id':str(uuid4()),
            'generacion_id':str(uuid4()),'recurso_id':str(self.archivo.pk),'clave_s3':'cloudvault/dani/publicaciones/x'})
        with patch('storage.repositorio_papelera.LogAuditoria.objects') as auditoria:
            eventos=auditoria.using.return_value.filter.return_value
            solicitudes=MagicMock()
            solicitudes.order_by.return_value.__getitem__.return_value=[solicitud]
            cierre=MagicMock();cierre.exists.return_value=False
            eventos.filter.side_effect=lambda **kw: solicitudes if kw.get('accion')=='PAPELERA_PURGA_SOLICITADA' else cierre
            self.assertTrue(self.repo.purga_pendiente(self.archivo))
            kw=eventos.filter.call_args.kwargs
            self.assertEqual(kw['detalles__operacion_id'],solicitud.detalles['operacion_id'])
            self.assertEqual(kw['detalles__generacion_id'],solicitud.detalles['generacion_id'])
            cierre.exists.return_value=True
            solicitudes.order_by.return_value.__getitem__.return_value=[solicitud]
            self.assertFalse(self.repo.purga_pendiente(self.archivo))

    def test_intencion_incompatible_falla_cerrada(self):
        with patch('storage.repositorio_papelera.LogAuditoria.objects') as auditoria:
            eventos=auditoria.using.return_value.filter.return_value
            solicitudes=MagicMock()
            solicitudes.order_by.return_value.__getitem__.return_value=[SimpleNamespace(
                detalles={'version':2})]
            eventos.filter.return_value=solicitudes
            with self.assertRaises(ErrorPapelera):
                self.repo.purga_pendiente(self.archivo)

    def test_seleccion_de_lote_bloquea_purgas_ajenas_y_permite_su_propio_servicio(self):
        operacion = str(uuid4())
        evento = SimpleNamespace(accion="PAPELERA_VACIADO_INICIADO",
                                 detalles={"operacion_id": operacion})
        with patch("storage.repositorio_papelera.LogAuditoria.objects") as auditoria:
            eventos = MagicMock()
            eventos.order_by.return_value.__getitem__.return_value = [evento]
            cierre = MagicMock()
            cierre.exists.return_value = False
            auditoria.using.return_value.filter.side_effect = [eventos, cierre, eventos, cierre]

            self.assertTrue(self.repo.lote_purga_pendiente(
                self.org, self.archivo.pk, excluir_operacion="otra-operacion"))
            self.assertFalse(self.repo.lote_purga_pendiente(
                self.org, self.archivo.pk, excluir_operacion=operacion))

    def test_ultimo_evento_de_version_desconocida_falla_cerrado(self):
        evento = SimpleNamespace(detalles={"version":2, "generacion_id":str(uuid4()),
                                           "recurso_id":str(self.archivo.pk)})
        with patch('storage.repositorio_papelera.LogAuditoria.objects') as auditoria:
            auditoria.using.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = evento
            with self.assertRaises(ErrorPapelera):
                self.repo.ultimo_evento(self.archivo)

    def test_generar_o_reutilizar_intencion_adopta_legado_y_reusa_pending(self):
        actor = uuid4()
        self.archivo.en_papelera = True
        self.archivo.fecha_papelera = AHORA
        self.archivo.clave_s3 = "cloudvault/dani/publicaciones/legado"
        with patch.object(self.repo, "intencion_pendiente", return_value=None), \
             patch.object(self.repo, "ultimo_evento", return_value=None), \
             patch.object(self.repo, "evento_restauracion") as adoptar, \
             patch.object(self.repo, "_crear_evento") as crear:
            intencion = self.repo.generar_o_reutilizar_intencion(self.archivo, actor)
        self.assertEqual(adoptar.call_args.args[3], "PAPELERA_GENERACION_ADOPTADA")
        self.assertEqual(crear.call_args.args[2], "PAPELERA_PURGA_SOLICITADA")
        self.assertEqual(intencion["generacion_id"], adoptar.call_args.args[2])
        self.assertEqual(intencion["fecha_papelera"], AHORA.isoformat())
        solicitud = SimpleNamespace(detalles=intencion)
        with patch.object(self.repo, "intencion_pendiente", return_value=solicitud), \
             patch.object(self.repo, "ultimo_evento", return_value=SimpleNamespace(
                 accion="PAPELERA_GENERACION_ADOPTADA",
                 detalles={"version":1, "generacion_id":intencion["generacion_id"],
                           "recurso_id":str(self.archivo.pk)})):
            self.assertEqual(self.repo.generar_o_reutilizar_intencion(self.archivo, actor), intencion)

    def test_generar_intencion_pendiente_no_reusa_clave_cambiada(self):
        self.archivo.en_papelera = True
        self.archivo.fecha_papelera = AHORA
        self.archivo.clave_s3 = "cloudvault/dani/publicaciones/nueva"
        intencion = {"version":1, "operacion_id":str(uuid4()), "generacion_id":str(uuid4()),
                     "recurso_id":str(self.archivo.pk), "fecha_papelera":AHORA.isoformat(),
                     "clave_s3":"cloudvault/dani/publicaciones/antigua"}
        with patch.object(self.repo, "intencion_pendiente", return_value=SimpleNamespace(detalles=intencion)), \
             patch.object(self.repo, "ultimo_evento", return_value=SimpleNamespace(
                 accion="PAPELERA_ENVIADO", detalles={"version":1,
                     "generacion_id":intencion["generacion_id"], "recurso_id":str(self.archivo.pk)})):
            with self.assertRaises(ErrorPapelera):
                self.repo.generar_o_reutilizar_intencion(self.archivo, self.actor)

    def test_cierre_revalida_generacion_y_referencias(self):
        actor, generacion = uuid4(), str(uuid4())
        self.archivo.en_papelera = True
        self.archivo.fecha_papelera = AHORA
        self.archivo.clave_s3 = "cloudvault/dani/publicaciones/recurso"
        self.archivo.delete = MagicMock()
        intencion = {"version":1, "operacion_id":str(uuid4()), "generacion_id":generacion,
                     "recurso_id":str(self.archivo.pk), "fecha_papelera":AHORA.isoformat(),
                     "clave_s3":self.archivo.clave_s3}
        solicitud = SimpleNamespace(detalles=intencion)
        evento = SimpleNamespace(accion="PAPELERA_ENVIADO",
                                 detalles={"version":1, "generacion_id":generacion,
                                           "recurso_id":str(self.archivo.pk)})
        eventos = MagicMock()
        eventos.filter.return_value.order_by.return_value.first.return_value = None
        with patch.object(self.repo, "intencion_pendiente", return_value=solicitud), \
             patch.object(self.repo, "ultimo_evento", return_value=evento), \
             patch.object(self.repo, "referencia_incompatible", return_value=False), \
             patch.object(self.repo, "_eventos_archivo", return_value=eventos), \
             patch("storage.repositorio_papelera.LogAuditoria.objects") as auditoria:
            self.repo.cerrar_purga(self.archivo, actor, intencion)
            self.archivo.delete.assert_called_once_with(using="default")
            auditoria.using.return_value.create.assert_called_once()
            detalles_cierre = auditoria.using.return_value.create.call_args.kwargs["detalles"]
            self.assertEqual(detalles_cierre["fecha_papelera"], AHORA.isoformat())
        with patch.object(self.repo, "intencion_pendiente", return_value=solicitud), \
             patch.object(self.repo, "ultimo_evento", return_value=SimpleNamespace(
                 accion="PAPELERA_ENVIADO", detalles={"version":1, "generacion_id":str(uuid4()),
                                                       "recurso_id":str(self.archivo.pk)})), \
             patch.object(self.repo, "referencia_incompatible", return_value=False), \
             patch.object(self.repo, "_eventos_archivo", return_value=eventos):
            with self.assertRaises(ErrorPapelera):
                self.repo.cerrar_purga(self.archivo, actor, intencion)
        with patch.object(self.repo, "intencion_pendiente", return_value=solicitud), \
             patch.object(self.repo, "ultimo_evento", return_value=evento), \
             patch.object(self.repo, "referencia_incompatible", return_value=True), \
             patch.object(self.repo, "_eventos_archivo", return_value=eventos):
            with self.assertRaises(ErrorPapelera):
                self.repo.cerrar_purga(self.archivo, actor, intencion)

    def test_recuperacion_pendiente_tiene_paginacion_acotada(self):
        evento = SimpleNamespace(id=3, detalles={"version":1, "operacion_id":str(uuid4()),
            "generacion_id":str(uuid4()), "recurso_id":str(self.archivo.pk),
            "clave_s3":"cloudvault/dani/publicaciones/x"})
        with patch("storage.repositorio_papelera.LogAuditoria.objects") as auditoria:
            eventos = auditoria.using.return_value.filter.return_value
            solicitudes = MagicMock()
            page = MagicMock()
            solicitudes.filter.return_value = page
            page.order_by.return_value.__getitem__.return_value = [evento]
            cierre = MagicMock(); cierre.exists.return_value = False
            eventos.filter.side_effect = lambda **kw: solicitudes if kw.get("accion") == "PAPELERA_PURGA_SOLICITADA" else cierre
            encontrados = list(self.repo.recorrer_intenciones_pendientes(self.org, limite=1))
        self.assertEqual(encontrados, [evento])
        self.assertEqual(page.order_by.call_args.args, ("id",))
        page.order_by.return_value.__getitem__.assert_called_once_with(slice(None, 100, None))

class CalendarioPapeleraTests(SimpleTestCase):
    def test_fecha_nula_conserva_cero_dias_y_no_inventa_vencimiento(self):
        from storage.serializers import PapeleraSerializer

        serializer = PapeleraSerializer()
        self.assertIsNone(serializer.get_expira_en(SimpleNamespace(fecha_papelera=None)))
        self.assertEqual(serializer.get_dias_restantes(SimpleNamespace(fecha_papelera=None)), 0)

    def test_fechas_limite_y_nulas_con_mismo_reloj(self):
        from datetime import timedelta
        from storage.serializers import PapeleraSerializer
        base = dict(pk=uuid4(), id=uuid4(), nombre='archivo.txt', tamano_bytes=1, carpeta_id=None)
        elementos = [SimpleNamespace(**base, fecha_papelera=AHORA-timedelta(days=29)),
                     SimpleNamespace(**base, fecha_papelera=AHORA-timedelta(days=30)),
                     SimpleNamespace(**base, fecha_papelera=None)]
        with patch('storage.serializers.timezone.now', return_value=AHORA) as reloj:
            datos = PapeleraSerializer(elementos, many=True).data
        self.assertEqual([e['dias_restantes'] for e in datos], [1, 0, 0])
        self.assertIsNone(datos[2]['eliminado_en'])
        self.assertIsNone(datos[2]['expira_en'])
        reloj.assert_called_once()

    def test_orden_estable_con_nulos_al_final(self):
        vista = PapeleraViewSet()
        with patch.object(vista, '_ambito', return_value=Ambito(uuid4(), 0)), \
             patch('storage.views.Archivo.objects') as archivos:
            vista.get_queryset()
        orden = archivos.filter.return_value.order_by.call_args.args
        self.assertEqual(orden[1], 'id')
        self.assertTrue(orden[0].descending)
        self.assertTrue(orden[0].nulls_last)

class RestauracionFaseDosTests(BasePapeleraTests):
    def setUp(self):
        super().setUp()
        self.repo.fila.en_papelera = True
        self.repo.fila.fecha_papelera = AHORA

    def test_restaura_con_capacidad_exacta_y_repite_sin_otro_evento(self):
        self.repo.cuota = (1000, 700, 100)
        self.servicio.restaurar(**self.datos)
        self.assertFalse(self.repo.fila.en_papelera)
        self.assertIsNone(self.repo.fila.fecha_papelera)
        eventos = len(self.repo.eventos)
        self.servicio.restaurar(**self.datos)
        self.assertEqual(len(self.repo.eventos), eventos)

    def test_reservas_impiden_restaurar_sin_mutacion(self):
        self.repo.cuota = (1000, 701, 100)
        with self.assertRaises(ErrorPapelera) as exc: self.servicio.restaurar(**self.datos)
        self.assertEqual(exc.exception.detail['error']['code'], 'CUOTA_EXCEDIDA')
        self.assertTrue(self.repo.fila.en_papelera)
        self.assertEqual(self.repo.eventos, [])

    def test_colision_pendiente_y_roles_no_reactivan(self):
        for campo, valor in [('colision',True),('pendiente',True),('rol',2)]:
            with self.subTest(campo=campo):
                setattr(self.repo,campo,valor)
                with self.assertRaises((ErrorPapelera,PermissionDenied)): self.servicio.restaurar(**self.datos)
                self.assertTrue(self.repo.fila.en_papelera)
                setattr(self.repo,campo,0 if campo=='rol' else False)

    def test_fallo_auditoria_y_commit_revierte_restauracion(self):
        for campo in ['falla_auditoria','falla_commit']:
            setattr(self.repo,campo,True)
            with self.assertRaises(ErrorPapelera): self.servicio.restaurar(**self.datos)
            self.assertTrue(self.repo.fila.en_papelera)
            setattr(self.repo,campo,False)

    def test_sin_fecha_no_inventa_retencion(self):
        self.repo.fila.fecha_papelera=None
        with self.assertRaises(ErrorPapelera): self.servicio.restaurar(**self.datos)
        self.assertTrue(self.repo.fila.en_papelera)

    def test_vacio_exige_espacio_libre(self):
        self.repo.fila.tamano_bytes=0
        self.repo.cuota=(100,100,0)
        with self.assertRaises(ErrorPapelera):self.servicio.restaurar(**self.datos)

    def test_listado_niveles_denegados_antes_de_consultar(self):
        vista=PapeleraViewSet()
        for nivel in (1,2):
            with patch.object(vista,'_ambito',return_value=SimpleNamespace(nivel_rol=nivel)), patch('storage.views.Archivo.objects') as archivos:
                with self.assertRaises(PermissionDenied):vista.get_queryset()
                archivos.filter.assert_not_called()

class DestinosYContratosTests(SimpleTestCase):
    def test_padre_ausente_permite_grant_directo(self):
        actor,org,padre=uuid4(),uuid4(),uuid4()
        archivo=SimpleNamespace(pk=uuid4(),carpeta_id=padre,organizacion_id=org)
        repo=RepositorioPapelera()
        with patch('storage.repositorio_papelera.Carpeta.objects') as carpetas, patch('storage.repositorio_papelera.connections') as conexiones:
            carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.return_value=None
            carpetas.using.return_value.filter.return_value.exists.return_value=False
            cursor=conexiones.__getitem__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value=[('write',)]
            self.assertEqual(repo.permisos(actor,archivo),['write'])
            self.assertIsNone(repo.destino(archivo,actor,3))

    def test_destino_sin_permiso_no_se_convierte_en_raiz(self):
        archivo=SimpleNamespace(pk=uuid4(),carpeta_id=uuid4(),organizacion_id=uuid4())
        repo=RepositorioPapelera()
        with patch('storage.repositorio_papelera.Carpeta.objects') as carpetas, patch.object(repo,'permisos',return_value=[]):
            carpetas.using.return_value.select_for_update.return_value.filter.return_value.first.return_value=SimpleNamespace(en_papelera=False,padre_id=None)
            with self.assertRaises(PermissionDenied):repo.destino(archivo,uuid4(),3)

    def test_conflicto_publicacion_se_traduce_a_409(self):
        from almacenamiento.errores import ConflictoNombreCarga,error_de_almacenamiento
        response=error_de_almacenamiento(ConflictoNombreCarga())
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.data['error']['code'],'VALIDATION_ERROR')

    def test_nombres_unicode_entre_tipos(self):
        from storage.repositorio_papelera import nombre_disponible
        with patch('storage.repositorio_papelera.Archivo.objects') as archivos,patch('storage.repositorio_papelera.Carpeta.objects') as carpetas:
            archivos.using.return_value.filter.return_value.values_list.return_value.iterator.return_value=iter([])
            carpetas.using.return_value.filter.return_value.values_list.return_value.iterator.return_value=iter(['CAFÉ'])
            self.assertFalse(nombre_disponible(uuid4(),None,'cafe\u0301'))

    def test_listado_avanzado_filtra_antes_de_paginar(self):
        vista=PapeleraViewSet();vista.request=SimpleNamespace(user=SimpleNamespace(pk=uuid4()))
        permitido,denegado=SimpleNamespace(pk=uuid4()),SimpleNamespace(pk=uuid4())
        with patch.object(vista,'_ambito',return_value=Ambito(uuid4(), 3)),patch('storage.views.Archivo.objects') as archivos,patch('storage.views.RepositorioPapelera') as repo:
            qs=archivos.filter.return_value
            qs.iterator.return_value=iter([permitido,denegado])
            repo.return_value.permisos.side_effect=[['read'],[]]
            vista.get_queryset()
            qs.filter.assert_called_once_with(pk__in=[permitido.pk])

    def test_listado_compartido_oculta_la_carpeta_inaccesible_antes_de_serializar(self):
        from storage.models import Archivo
        from storage.serializers import PapeleraSerializer

        ambito = Ambito(uuid4(), 3, "COMPARTIDO")
        actor = uuid4()
        archivo_id = uuid4()
        carpeta_id = uuid4()
        archivo = Archivo(id=archivo_id, nombre="informe.txt", tamano_bytes=1,
                          carpeta_id=carpeta_id, en_papelera=True)
        archivo.carpeta_visible = None
        vista = PapeleraViewSet()
        vista.request = SimpleNamespace(user=SimpleNamespace(pk=actor), query_params={})
        with (
            patch.object(vista, "_ambito", return_value=ambito),
            patch("storage.views.Archivo.objects") as archivos,
            patch("storage.views.RepositorioPapelera") as repo,
            patch("storage.views.carpetas_autorizadas") as autorizadas,
            patch("storage.views.con_carpeta_visible") as anotar,
        ):
            consulta = archivos.filter.return_value
            consulta.iterator.return_value = iter([archivo])
            repo.return_value.permisos.return_value = ["LECTURA"]

            vista.get_queryset()

            consulta.filter.assert_called_once_with(pk__in=[archivo_id])
            autorizadas.assert_called_once_with(ambito, actor)
            anotar.assert_called_once_with(consulta.filter.return_value, autorizadas.return_value)
        self.assertIsNone(PapeleraSerializer(archivo).data["carpeta_id"])
        del archivo.carpeta_visible
        self.assertEqual(PapeleraSerializer(archivo).data["carpeta_id"], str(carpeta_id))

    def test_vista_raices_no_oculta_archivo_si_la_raiz_no_es_visible(self):
        from auth_workspaces.models import LogAuditoria
        from storage.models import Carpeta

        for visible_raiz in (False, True):
            with self.subTest(visible_raiz=visible_raiz):
                actor, org, raiz_id = uuid4(), uuid4(), uuid4()
                archivo = SimpleNamespace(pk=uuid4())
                vista = PapeleraViewSet()
                vista.request = SimpleNamespace(
                    user=SimpleNamespace(pk=actor), query_params={"vista": "raices"})
                lote = SimpleNamespace(detalles={"raiz_id": str(raiz_id)})
                with patch.object(vista, "_ambito", return_value=Ambito(org, 3)), \
                     patch("storage.views.Archivo.objects") as archivos, \
                     patch("storage.views.RepositorioPapelera") as repo, \
                     patch.object(LogAuditoria, "objects") as auditoria, \
                     patch.object(Carpeta, "objects") as carpetas:
                    qs = archivos.filter.return_value
                    qs.iterator.side_effect = lambda: iter([archivo])
                    qs.filter.return_value.iterator.side_effect = lambda: iter([archivo])
                    repo.return_value.permisos.side_effect = [
                        ["read"], ["read"] if visible_raiz else []]
                    repo.return_value.ultimo_evento.return_value = SimpleNamespace(
                        detalles={"origen": "CARPETA", "operacion_id": "op-1"})
                    auditoria.filter.return_value.first.return_value = lote
                    auditoria.filter.return_value.exists.return_value = False
                    carpetas.filter.return_value.exists.return_value = True
                    carpetas.filter.return_value.first.return_value = SimpleNamespace(pk=raiz_id)

                    vista.get_queryset()

                    qs.filter.assert_called_once_with(pk__in=[archivo.pk])
                    if visible_raiz:
                        qs.filter.return_value.exclude.assert_called_once_with(
                            pk__in=[archivo.pk])
                    else:
                        qs.filter.return_value.exclude.assert_called_once_with(pk__in=[])
                    repo.return_value.ultimo_evento.assert_called_once_with(archivo)
                    self.assertEqual(repo.return_value.permisos.call_count, 2)


class ConflictoRestauracionTests(BasePapeleraTests):
    def test_conflicto_informa_campo_nombre_y_no_restaura(self):
        self.repo.fila.en_papelera=True
        self.repo.fila.fecha_papelera=AHORA
        self.repo.colision=True
        with self.assertRaises(ErrorPapelera) as error:
            self.servicio.restaurar(**self.datos)
        self.assertIn('nombre',error.exception.detail['error']['fields'])
        self.assertEqual(error.exception.status_code,409)
        self.assertTrue(self.repo.fila.en_papelera)
