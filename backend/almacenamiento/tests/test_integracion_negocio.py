"""Frontera y rutas con negocio simulado explícito; sin DB/.env/S3."""

from dataclasses import replace
from types import ModuleType, SimpleNamespace
import sys
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import include, path, resolve
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIClient

from almacenamiento.conexion_negocio import (
    PARAMETROS_PROVEEDOR, crear_servicios_almacenamiento, validar_proveedor,
)
from almacenamiento.configuracion_inicio import servicios_compartidos
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.integracion import DestinoAutorizado
from almacenamiento.persistencia import IntegridadCarga
from almacenamiento.rutas_integracion import rutas_almacenamiento_y_negocio
from almacenamiento.views import ConfirmarCargaView, DescargaView, IniciarCargaView


def proveedor_simulado():
    return SimpleNamespace(using="default", **{
        nombre: Mock() for nombre in PARAMETROS_PROVEEDOR
    })


class ConexionNegocioTests(SimpleTestCase):
    def test_fabrica_valida_envuelve_sin_ejecutar_operaciones_de_negocio(self):
        proveedor = proveedor_simulado()
        fabrica = Mock(return_value=proveedor)
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=fabrica):
            puente = servicios_compartidos()
        self.assertIs(puente.servicios, proveedor)
        fabrica.assert_called_once_with()
        for nombre in PARAMETROS_PROVEEDOR:
            getattr(proveedor, nombre).assert_not_called()

    def test_fabrica_importable_se_carga_por_el_mismo_punto_de_entrada(self):
        modulo = ModuleType("proveedor_pruebas")
        modulo.crear = Mock(return_value=proveedor_simulado())
        with patch.dict(sys.modules, {modulo.__name__: modulo}), \
                override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY="proveedor_pruebas.crear"):
            puente = crear_servicios_almacenamiento()
        self.assertIs(puente.servicios, modulo.crear.return_value)
        modulo.crear.assert_called_once_with()

    def test_cada_operacion_ausente_o_no_callable_rechaza_el_proveedor(self):
        for nombre in PARAMETROS_PROVEEDOR:
            for valor in (None, 42):
                proveedor = proveedor_simulado()
                setattr(proveedor, nombre, valor)
                with self.subTest(nombre=nombre, valor=valor), \
                        override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=lambda: proveedor), \
                        self.assertRaises(ErrorCarga) as error:
                    servicios_compartidos()
                self.assertEqual(error.exception.codigo, CodigoError.SERVICE_UNAVAILABLE)

    def test_alias_sql_distinto_y_proveedor_nulo_no_son_compatibles(self):
        proveedor = proveedor_simulado()
        proveedor.using = "otra_base"
        for valor in (proveedor, None):
            with self.subTest(valor=type(valor).__name__), \
                    override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=lambda: valor), \
                    self.assertRaises(ErrorCarga):
                servicios_compartidos()

    def test_firma_no_admite_parametros_posicionales_o_requisitos_extra(self):
        def solo_posicional(organizacion_id, /):
            pass

        def requisito_extra(*, organizacion_id, otro):
            pass

        for operacion in (solo_posicional, requisito_extra):
            proveedor = proveedor_simulado()
            proveedor.leer_cuota = operacion
            with self.subTest(operacion=operacion.__name__), self.assertRaises(TypeError):
                validar_proveedor(proveedor)

    def test_fabrica_y_operaciones_async_se_rechazan_sin_crear_corutinas(self):
        async def asincrona(**kwargs):
            raise AssertionError("Nunca ejecutar")

        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=asincrona), self.assertRaises(ErrorCarga):
            servicios_compartidos()
        proveedor = proveedor_simulado()
        proveedor.autorizar_descarga = asincrona
        with self.assertRaises(ValueError):
            validar_proveedor(proveedor)

    def test_no_admite_cargador_recursivo_ni_fabrica_con_argumentos(self):
        for fabrica in (crear_servicios_almacenamiento,
                        "almacenamiento.conexion_negocio.crear_servicios_almacenamiento",
                        lambda obligatorio: proveedor_simulado()):
            with self.subTest(fabrica=type(fabrica).__name__), \
                    override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=fabrica), self.assertRaises(ErrorCarga):
                servicios_compartidos()

    def test_fallo_de_constructor_se_traduce_sin_exponer_su_mensaje(self):
        fabrica = Mock(side_effect=RuntimeError("synthetic-private-password"))
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=fabrica), self.assertRaises(ErrorCarga) as error:
            servicios_compartidos()
        self.assertEqual(error.exception.codigo, CodigoError.SERVICE_UNAVAILABLE)
        self.assertNotIn("synthetic-private", str(error.exception))
        self.assertIsNone(error.exception.__cause__)

    def test_puente_no_inventa_organizacion_ni_convierte_usuario_entero(self):
        actor, carpeta = uuid4(), uuid4()
        destino = DestinoAutorizado(actor, uuid4(), carpeta)
        proveedor = proveedor_simulado()
        proveedor.resolver_destino.return_value = destino
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=lambda: proveedor):
            puente = servicios_compartidos()
        self.assertEqual(puente.resolver_destino(solicitante_id=actor, carpeta_id=carpeta), destino)
        with self.assertRaises(IntegridadCarga):
            puente.resolver_destino(solicitante_id=1, carpeta_id=carpeta)
        proveedor.resolver_destino.assert_called_once_with(solicitante_id=actor, carpeta_id=carpeta)
        proveedor.resolver_destino.return_value = replace(destino, organizacion_id=1)
        with self.assertRaises(IntegridadCarga):
            puente.resolver_destino(solicitante_id=actor, carpeta_id=carpeta)

    def test_proveedor_incompleto_da_503_en_las_tres_rutas_sin_sql_o_s3(self):
        client = APIClient()
        client.force_authenticate(SimpleNamespace(pk=uuid4(), is_authenticated=True))
        proveedor = proveedor_simulado()
        proveedor.registrar_archivo = None
        archivo = str(uuid4())
        with override_settings(ALMACENAMIENTO_SERVICIOS_FACTORY=lambda: proveedor), \
                patch("almacenamiento.views.cliente_firmador") as s3:
            respuestas = [
                client.post("/api/v1/archivos/iniciar-carga/",
                            {"nombre": "prueba.txt", "tamano_bytes": 5, "tipo_mime": "text/plain"}, format="json"),
                client.post(f"/api/v1/archivos/{archivo}/confirmar-carga/", {}, format="json"),
                client.get(f"/api/v1/archivos/{archivo}/descarga/"),
            ]
        s3.assert_not_called()
        for respuesta in respuestas:
            self.assertEqual(respuesta.status_code, 503)
            self.assertEqual(respuesta.data["error"]["code"], "SERVICE_UNAVAILABLE")
        for nombre in PARAMETROS_PROVEEDOR:
            operacion = getattr(proveedor, nombre)
            if callable(operacion):
                operacion.assert_not_called()


class ArchivosSimuladosViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({"data": {"origen": "negocio-simulado"}})

    def retrieve(self, request, pk=None):
        return Response({"data": {"id": pk}})

    def partial_update(self, request, pk=None):
        return Response({"data": {"id": pk}})

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        return Response({"data": {"id": pk}})


class RutasIntegracionTests(SimpleTestCase):
    def setUp(self):
        router = DefaultRouter()
        router.register("archivos", ArchivosSimuladosViewSet, basename="archivo")
        negocio = ModuleType("negocio_simulado.urls")
        negocio.urlpatterns = router.urls
        self.negocio = negocio
        self.registro = patch.dict(sys.modules, {negocio.__name__: negocio})
        self.registro.start()
        self.addCleanup(self.registro.stop)

    def urlconf(self):
        modulo = ModuleType("rutas_integracion_simuladas")
        modulo.urlpatterns = [
            path("api/v1/auth/", include("auth_workspaces.urls")),
            *rutas_almacenamiento_y_negocio(),
        ]
        return modulo

    @override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=["negocio_simulado.urls"])
    def test_carga_confirmacion_descarga_tienen_prioridad_sobre_router(self):
        modulo = self.urlconf()
        archivo = str(uuid4())
        for ruta, vista in (("iniciar-carga/", IniciarCargaView),
                            (f"{archivo}/confirmar-carga/", ConfirmarCargaView),
                            (f"{archivo}/descarga/", DescargaView)):
            with self.subTest(ruta=ruta):
                self.assertIs(resolve("/api/v1/archivos/"+ruta, urlconf=modulo).func.view_class, vista)

    @override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=["negocio_simulado.urls"])
    def test_listado_detalle_renombrado_y_movimiento_siguen_en_negocio(self):
        modulo = self.urlconf()
        archivo = str(uuid4())
        for ruta, nombre in (("", "archivo-list"), (f"{archivo}/", "archivo-detail"),
                            (f"{archivo}/mover/", "archivo-mover")):
            self.assertEqual(resolve("/api/v1/archivos/"+ruta, urlconf=modulo).url_name, nombre)
        self.assertEqual(resolve(f"/api/v1/archivos/{archivo}/", urlconf=modulo).func.actions["patch"],
                         "partial_update")

    @override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=["negocio_simulado.urls"],
                       ALMACENAMIENTO_SERVICIOS_FACTORY="")
    def test_post_inicio_alcanza_almacenamiento_y_no_devuelve_405_del_router(self):
        with override_settings(ROOT_URLCONF=self.urlconf()):
            cliente = APIClient()
            cliente.force_authenticate(SimpleNamespace(pk=uuid4(), is_authenticated=True))
            respuesta = cliente.post("/api/v1/archivos/iniciar-carga/",
                                     {"nombre": "x.txt", "tamano_bytes": 1, "tipo_mime": "text/plain"},
                                     format="json")
            self.assertEqual(respuesta.status_code, 503)
            self.assertEqual(respuesta.data["error"]["code"], "SERVICE_UNAVAILABLE")
            self.assertEqual(cliente.get("/api/v1/archivos/").status_code, 200)

    def test_configuracion_ausente_no_importa_apps_de_otras_ramas(self):
        with override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=[]):
            rutas = rutas_almacenamiento_y_negocio()
        self.assertEqual(len(rutas), 1)
        self.assertIs(resolve("/api/v1/archivos/iniciar-carga/").func.view_class, IniciarCargaView)

    def test_no_reemplaza_autenticacion_existente(self):
        with override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=["negocio_simulado.urls"]):
            modulo = self.urlconf()
        self.assertEqual(resolve("/api/v1/auth/login/", urlconf=modulo).func.__module__, "auth_workspaces.views")

    def test_configuracion_invalida_no_omite_silenciosamente_el_negocio(self):
        for valor in (None, "negocio_simulado.urls", [None], ["sin_puntos"],
                      ["negocio_simulado.urls", "negocio_simulado.urls"],
                      ["almacenamiento.urls"], ["config.urls"], ["no_existe.urls"]):
            with self.subTest(valor=valor), override_settings(ALMACENAMIENTO_URLCONFS_NEGOCIO=valor), \
                    self.assertRaises(ImproperlyConfigured):
                rutas_almacenamiento_y_negocio()

    def test_demuestra_colision_si_el_router_precede_a_las_rutas_propias(self):
        incorrecto = ModuleType("rutas_incorrectas_simuladas")
        incorrecto.urlpatterns = [
            path("api/v1/", include(self.negocio)),
            path("api/v1/archivos/", include("almacenamiento.urls")),
        ]
        match = resolve("/api/v1/archivos/iniciar-carga/", urlconf=incorrecto)
        self.assertEqual(match.url_name, "archivo-detail")
        self.assertEqual(match.kwargs, {"pk": "iniciar-carga"})
