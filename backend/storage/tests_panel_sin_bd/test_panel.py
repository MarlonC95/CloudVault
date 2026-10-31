from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock, patch
from uuid import UUID

from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from auth_workspaces.models import Usuario
from auth_workspaces.views import PerfilView
from almacenamiento.inicio import ServicioInicioCargas
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.confirmacion import ServicioConfirmacionCargas
from almacenamiento.integracion import DestinoAutorizado, resolver_destino_en_organizacion
from almacenamiento.errores import ErrorCarga
from almacenamiento.serializers import IniciarCargaInputSerializer
from common.ambito import resolver_organizacion
from storage.servicios import ProveedorStorage
from storage.views import ArchivoViewSet, CarpetaViewSet

A = UUID("a0000000-0000-4000-8000-000000000001")
B = UUID("a0000000-0000-4000-8000-000000000002")
ORG = UUID("b0000000-0000-4000-8000-000000000001")
OTRA = UUID("b0000000-0000-4000-8000-000000000002")


class EspaciosHTTPTests(SimpleTestCase):
    def setUp(self):
        self.cuenta = Usuario(id=A, is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.cuenta)
        self.usuarios = self.enterContext(patch("auth_workspaces.permisos_administracion.Usuario.objects"))
        self.usuarios.only.return_value.get.return_value = self.cuenta
        self.miembros = self.enterContext(patch("auth_workspaces.espacios_disponibles.MiembroOrganizacion.objects"))
        self.lista = self.miembros.filter.return_value.order_by.return_value
        self.lista.count.return_value = 2
        self.lista.__getitem__.return_value.values.return_value = [
            {"organizacion_id": ORG, "nivel_rol": 1}, {"organizacion_id": OTRA, "nivel_rol": 3}]
        self.orgs = self.enterContext(patch("auth_workspaces.espacios_disponibles.Organizacion.objects"))
        self.orgs.filter.return_value.values_list.return_value = [(ORG, "Equipo A"), (OTRA, "Equipo B")]
        self.ruta = "/api/v1/organizaciones/disponibles/"

    def test_solo_membresias_actor_con_proyeccion_publica_y_ruta_produccion(self):
        r = self.client.get(self.ruta)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["results"], [
            {"id": str(ORG), "nombre": "Equipo A", "nivel_rol": 1},
            {"id": str(OTRA), "nombre": "Equipo B", "nivel_rol": 3}])
        self.miembros.filter.assert_called_once_with(usuario_id=A)
        self.assertEqual(r["Cache-Control"], "no-store")
        self.miembros.create.assert_not_called()
        self.orgs.create.assert_not_called()

    def test_anonimo_inactivo_2fa_rechazados_sin_listar(self):
        for campo in ("is_active", "is_2fa_enabled"):
            setattr(self.cuenta, campo, campo == "is_2fa_enabled")
            self.assertEqual(self.client.get(self.ruta).status_code, 401)
            setattr(self.cuenta, campo, campo == "is_active")
        self.assertEqual(APIClient().get(self.ruta).status_code, 401)
        self.miembros.filter.assert_not_called()

    def test_cero_membresias_no_crea_espacio(self):
        self.lista.count.return_value = 0
        self.lista.__getitem__.return_value.values.return_value = []
        r = self.client.get(self.ruta)
        self.assertEqual(r.json()["data"]["results"], [])
        self.orgs.filter.assert_not_called()
        self.orgs.create.assert_not_called()

    def test_query_estricta_y_paginacion(self):
        for query in ("?usuario_id="+str(B), "?page=0", "?page_size=101", "?page=1&page=2", "?page=2"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.ruta + query).status_code, 400)
        self.lista.count.return_value = 101
        r = self.client.get(self.ruta + "?page_size=100")
        self.assertIn("page=2", r.json()["data"]["next"])

    def test_rol_desconocido_falla_cerrado(self):
        self.lista.__getitem__.return_value.values.return_value = [{"organizacion_id": ORG, "nivel_rol": 9}]
        self.assertEqual(self.client.get(self.ruta).status_code, 503)


class AislamientoPanelTests(SimpleTestCase):
    def test_perfil_respeta_organizacion_y_no_oculta_rechazo(self):
        vista = PerfilView()
        vista.request = SimpleNamespace(query_params={"organizacion_id": str(ORG)})
        with patch("auth_workspaces.views.resolver_organizacion", side_effect=NotFound()):
            with self.assertRaises(NotFound):
                vista._resolver_ambito(SimpleNamespace(pk=A))
        vista.request.query_params["organizacion_id"] = ""
        with self.assertRaises(ValidationError):
            vista._resolver_ambito(SimpleNamespace(pk=A))

    def test_rol_invalido_no_lee_ni_escribe(self):
        for nivel in (9, -1, None, True, "0"):
            for escritura in (False, True):
                with patch("common.ambito._membresias", return_value=[(ORG, nivel)]), self.assertRaises(PermissionDenied):
                    resolver_organizacion(SimpleNamespace(pk=A), ORG, escritura=escritura)

    def test_ambito_explicito_multiorganizacion_y_ajena(self):
        with patch("common.ambito._membresias", return_value=[(ORG, 1), (OTRA, 3)]):
            self.assertEqual(resolver_organizacion(SimpleNamespace(pk=A), ORG).organizacion_id, ORG)
            with self.assertRaises(ValidationError):
                resolver_organizacion(SimpleNamespace(pk=A))
            with self.assertRaises(NotFound):
                resolver_organizacion(SimpleNamespace(pk=A), A)
            with self.assertRaises(PermissionDenied):
                resolver_organizacion(SimpleNamespace(pk=A), ORG, escritura=True)

    def test_listados_organizacion_incluyen_otro_creador_y_filtran_otro_ambito(self):
        class Filas(list):
            def filter(self, **filtros):
                return Filas(f for f in self if all(f.get(k) == v for k, v in filtros.items()))
            def select_related(self, *args): return self
            def order_by(self, *args): return self
        filas = Filas([
            {"organizacion_id": ORG, "en_papelera": False, "propietario_id": B},
            {"organizacion_id": OTRA, "en_papelera": False, "propietario_id": A},
            {"organizacion_id": ORG, "en_papelera": True, "propietario_id": A}])
        for vista, modelo in ((ArchivoViewSet, "Archivo"), (CarpetaViewSet, "Carpeta")):
            instancia = vista()
            instancia.action = "list"
            instancia.request = SimpleNamespace(user=SimpleNamespace(pk=A), query_params={"organizacion_id": str(ORG)}, method="GET")
            with patch("common.ambito._membresias", return_value=[(ORG, 1)]), \
                    patch(f"storage.views.{modelo}.objects", filas):
                resultado = instancia.get_queryset()
            self.assertEqual(len(resultado), 1)
            self.assertEqual(resultado[0]["propietario_id"], B)


class DestinoOrganizacionTests(SimpleTestCase):
    def test_inicio_revalida_mismo_ambito_bajo_bloqueo_antes_de_reservar(self):
        servicios = SimpleNamespace(using="default",
            resolver_destino_organizacion=Mock(side_effect=[DestinoAutorizado(A, ORG, None), PermissionDenied()]),
            bloquear_cuota=Mock(return_value=nullcontext()))
        repo = Mock(using="default")
        repo.limitar_inicios.return_value = nullcontext()
        repo.unidad_de_trabajo.return_value = nullcontext()
        firmador = Mock()
        servicio = ServicioInicioCargas(servicios_factory=lambda: servicios, firmador_factory=lambda: firmador, repositorio=repo)
        with patch("almacenamiento.inicio.transaction.atomic", return_value=nullcontext()), self.assertRaises(PermissionDenied):
            servicio.iniciar(solicitante_id=A, datos={"nombre": "ensayo.txt", "tipo_mime": "text/plain", "tamano_bytes": 1, "organizacion_id": str(ORG)})
        self.assertEqual(servicios.resolver_destino_organizacion.call_count, 2)
        for llamada in servicios.resolver_destino_organizacion.call_args_list:
            self.assertEqual(llamada.kwargs, {"solicitante_id": A, "organizacion_id": ORG, "carpeta_id": None})
        repo.crear_sesion.assert_not_called()
        firmador.firmar_put.assert_not_called()
        firmador.cerrar.assert_called_once()

    def setUp(self):
        self.proveedor = ProveedorStorage()
        self.miembros = self.enterContext(patch("storage.servicios.MiembroOrganizacion.objects"))
        self.rol = self.miembros.using.return_value.filter.return_value.values_list.return_value.first
        self.rol.return_value = 2
        self.carpetas = self.enterContext(patch("storage.servicios.Carpeta.objects"))
        self.existe = self.carpetas.using.return_value.filter.return_value.exists
        self.existe.return_value = True

    def test_raiz_explicita_y_carpeta_con_membresia_vigente(self):
        for carpeta in (None, B):
            destino = self.proveedor.resolver_destino_organizacion(solicitante_id=A, carpeta_id=carpeta, organizacion_id=ORG)
            self.assertEqual(destino, DestinoAutorizado(A, ORG, carpeta))
        self.carpetas.using.return_value.filter.assert_called_once_with(pk=B, organizacion_id=ORG, en_papelera=False)

    def test_sin_membresia_lector_rol_invalido_o_carpeta_cruzada(self):
        for rol in (None, 1, 9, True):
            self.rol.return_value = rol
            with self.assertRaises(PermissionDenied):
                self.proveedor.resolver_destino_organizacion(solicitante_id=A, carpeta_id=None, organizacion_id=ORG)
        self.rol.return_value = 3
        self.existe.return_value = False
        with self.assertRaises(ErrorCarga):
            self.proveedor.resolver_destino_organizacion(solicitante_id=A, carpeta_id=B, organizacion_id=ORG)

    def test_puente_no_acepta_otro_ambito_ni_actor(self):
        proveedor = SimpleNamespace(using="default", resolver_destino_organizacion=Mock(return_value=DestinoAutorizado(A, OTRA, None)))
        puente = ServiciosCompartidosValidados(proveedor)
        with self.assertRaises(ErrorCarga):
            puente.resolver_destino_organizacion(solicitante_id=A, carpeta_id=None, organizacion_id=ORG)
        proveedor.resolver_destino_organizacion.return_value = DestinoAutorizado(B, ORG, None)
        with self.assertRaises(ErrorCarga):
            puente.resolver_destino_organizacion(solicitante_id=A, carpeta_id=None, organizacion_id=ORG)

    def test_confirmacion_usa_organizacion_persistida_y_rechaza_membresia_retirada(self):
        sesion = SimpleNamespace(solicitante_id=A, carpeta_id=None, organizacion_id=ORG)
        servicio = ServicioConfirmacionCargas(servicios_factory=None, cliente_factory=None, verificador=None, maximo_bytes=1)
        servicio._destino(self.proveedor, sesion)
        self.rol.return_value = None
        with self.assertRaises(PermissionDenied):
            servicio._destino(self.proveedor, sesion)

    def test_proveedor_legacy_solo_si_devuelve_mismo_destino(self):
        proveedor = SimpleNamespace(resolver_destino=Mock(return_value=DestinoAutorizado(A, ORG, None)))
        self.assertEqual(resolver_destino_en_organizacion(proveedor, solicitante_id=A, carpeta_id=None, organizacion_id=ORG).organizacion_id, ORG)
        proveedor.resolver_destino.return_value = DestinoAutorizado(A, OTRA, None)
        with self.assertRaises(ErrorCarga):
            resolver_destino_en_organizacion(proveedor, solicitante_id=A, carpeta_id=None, organizacion_id=ORG)

    def test_input_uuid_org_estricto(self):
        datos = {"nombre": "ensayo.txt", "tipo_mime": "text/plain", "tamano_bytes": 1, "organizacion_id": str(ORG)}
        entrada = IniciarCargaInputSerializer(data=datos)
        self.assertTrue(entrada.is_valid(), entrada.errors)
        self.assertEqual(entrada.validated_data["organizacion_id"], ORG)
        for valor in (None, [], True, "otro"):
            self.assertFalse(IniciarCargaInputSerializer(data={**datos, "organizacion_id": valor}).is_valid())
