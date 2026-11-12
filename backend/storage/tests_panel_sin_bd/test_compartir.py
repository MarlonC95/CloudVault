from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from auth_workspaces.models import Usuario
from compartir.acceso import Acceso, acceso_usuario, dentro_del_enlace
from compartir.models import ESCRITURA, LECTURA
from compartir.views import _contenido
from storage.models import Archivo, Carpeta
from storage.servicios import ProveedorStorage


class DescargaCompartidaTests(SimpleTestCase):
    def setUp(self):
        self.archivo, self.org, self.actor, self.carpeta = (uuid4() for _ in range(4))
        self.fila = (
            self.archivo, self.org, self.carpeta, "informe.pdf", "publicaciones/informe",
            12, "application/pdf", "a" * 64,
        )
        self.conexion = MagicMock(in_atomic_block=True)
        self.cursor = self.conexion.cursor.return_value.__enter__.return_value
        self.enterContext(patch("storage.servicios.connections", {"default": self.conexion}))
        self.acceso = self.enterContext(patch("storage.servicios.acceso_usuario"))
        self.proveedor = ProveedorStorage()

    def descargar(self):
        return self.proveedor.autorizar_descarga(solicitante_id=self.actor, archivo_id=self.archivo)

    def test_miembro_autorizado_conserva_metadatos_checksum_y_bloqueos(self):
        for nivel in (0, 2, 3):
            with self.subTest(nivel=nivel):
                self.cursor.fetchone.return_value = (*self.fila, nivel, self.actor, None)
                archivo = self.descargar()
                self.assertEqual((archivo.archivo_id, archivo.organizacion_id, archivo.carpeta_id),
                                 (self.archivo, self.org, self.carpeta))
                self.assertEqual(archivo.checksum_sha256, self.fila[7])
                consulta, parametros = self.cursor.execute.call_args.args
                self.assertIn("FOR SHARE OF m", consulta)
                self.assertIn("FOR SHARE OF a", consulta)
                self.assertEqual(parametros, [self.actor, self.archivo])
        self.acceso.assert_not_called()

    def test_confirmacion_reutiliza_checksum_de_publicacion(self):
        checksum = "b" * 64
        self.proveedor._checksums[self.archivo] = checksum
        self.cursor.fetchone.return_value = (*self.fila[:-1], None, 0, self.actor, None)
        self.assertEqual(self.descargar().checksum_sha256, checksum)

    def test_lector_no_usa_concesion_externa_para_descargar_ni_subir(self):
        self.cursor.fetchone.return_value = (*self.fila, 1, self.actor, "COMPARTIDO")
        self.acceso.return_value = Acceso(ESCRITURA, True, self.org)
        with self.assertRaises(ErrorCarga) as descarga:
            self.descargar()
        self.assertEqual(descarga.exception.codigo, CodigoError.NO_ENCONTRADO)

        self.cursor.fetchall.return_value = [(self.org, 1)]
        with self.assertRaises(PermissionDenied):
            self.proveedor.resolver_destino(solicitante_id=self.actor, carpeta_id=self.carpeta)
        self.acceso.assert_not_called()

    def test_externo_descarga_solo_con_concesion_vigente_y_descarga_permitida(self):
        self.conexion.in_atomic_block = False
        self.cursor.fetchone.return_value = (*self.fila, None, uuid4(), None)
        for permiso, codigo in (
            (None, CodigoError.NO_ENCONTRADO),
            (Acceso(LECTURA, False, self.org), CodigoError.SIN_PERMISO),
        ):
            with self.subTest(codigo=codigo):
                self.acceso.return_value = permiso
                with self.assertRaises(ErrorCarga) as error:
                    self.descargar()
                self.assertEqual(error.exception.codigo, codigo)
        self.acceso.return_value = Acceso(LECTURA, True, self.org)
        self.assertEqual(self.descargar().archivo_id, self.archivo)
        self.acceso.assert_called_with(self.actor, archivo_id=self.archivo, using="default")
        consulta, _ = self.cursor.execute.call_args.args
        self.assertNotIn("FOR SHARE", consulta)

    def test_externo_con_permiso_de_escritura_conserva_carga_a_carpeta(self):
        self.cursor.fetchall.return_value = []
        self.acceso.return_value = Acceso(ESCRITURA, True, self.org)
        destino = self.proveedor.resolver_destino(solicitante_id=self.actor, carpeta_id=self.carpeta)
        self.assertEqual((destino.organizacion_id, destino.carpeta_id), (self.org, self.carpeta))

    def test_confirmacion_revalida_concesion_externa_en_la_organizacion_reservada(self):
        argumentos = {"solicitante_id": self.actor, "carpeta_id": self.carpeta, "organizacion_id": self.org}
        with patch("storage.servicios.MiembroOrganizacion.objects") as miembros:
            nivel = miembros.using.return_value.filter.return_value.values_list.return_value.first
            nivel.return_value = None
            self.acceso.return_value = Acceso(ESCRITURA, True, self.org)
            destino = self.proveedor.resolver_destino_organizacion(**argumentos)
            self.assertEqual((destino.organizacion_id, destino.carpeta_id), (self.org, self.carpeta))

            self.acceso.return_value = Acceso(ESCRITURA, True, uuid4())
            with self.assertRaises(ErrorCarga) as error:
                self.proveedor.resolver_destino_organizacion(**argumentos)
            self.assertEqual(error.exception.codigo, CodigoError.NO_ENCONTRADO)

            self.acceso.return_value = None
            with self.assertRaises(PermissionDenied):
                self.proveedor.resolver_destino_organizacion(**argumentos)

            nivel.return_value = 1
            self.acceso.reset_mock()
            with self.assertRaises(PermissionDenied):
                self.proveedor.resolver_destino_organizacion(**argumentos)
            self.acceso.assert_not_called()

    def test_miembro_compartido_sin_permiso_no_descarga_archivo_ajeno(self):
        self.cursor.fetchone.return_value = (*self.fila, 2, uuid4(), "COMPARTIDO")
        self.acceso.return_value = None
        with self.assertRaises(ErrorCarga) as error:
            self.descargar()
        self.assertEqual(error.exception.codigo, CodigoError.NO_ENCONTRADO)

        self.acceso.return_value = Acceso(LECTURA, True, self.org)
        self.assertEqual(self.descargar().archivo_id, self.archivo)

    def test_archivo_ausente_no_consulta_concesion(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(ErrorCarga) as error:
            self.descargar()
        self.assertEqual(error.exception.codigo, CodigoError.NO_ENCONTRADO)
        self.acceso.assert_not_called()


class GestionCompartidosHTTPTests(SimpleTestCase):
    def test_solo_propietario_puede_consultar_enlaces_y_permisos(self):
        org = uuid4()
        recurso = Archivo(id=uuid4(), organizacion_id=org)
        cliente = APIClient()
        cliente.force_authenticate(Usuario(id=uuid4(), is_active=True))
        with (
            patch("compartir.views._recurso_pedido", return_value=recurso),
            patch("common.ambito._membresias") as membresias,
            patch("compartir.views.EnlacePublico.objects") as enlaces,
            patch("compartir.views.PermisoRecurso.objects") as permisos,
        ):
            enlaces.filter.return_value.first.return_value = None
            permisos.select_related.return_value.filter.return_value.order_by.return_value = []
            for nivel in (1, 2, 3, None):
                with self.subTest(nivel=nivel):
                    membresias.return_value = [] if nivel is None else [(org, nivel)]
                    self.assertEqual(cliente.get("/api/v1/enlaces-compartidos/").status_code, 404)
                    self.assertEqual(cliente.get("/api/v1/permisos-recurso/").status_code, 404)
            enlaces.filter.assert_not_called()
            permisos.select_related.assert_not_called()

            membresias.return_value = [(org, 0)]
            self.assertEqual(cliente.get("/api/v1/enlaces-compartidos/").status_code, 200)
            self.assertEqual(cliente.get("/api/v1/permisos-recurso/").status_code, 200)


class AmbitoCompartidosTests(SimpleTestCase):
    def test_herencia_usa_el_ambito_del_recurso_para_la_carpeta_y_sus_ancestros(self):
        org, archivo, carpeta, usuario = (uuid4() for _ in range(4))
        conexion = MagicMock()
        cursor = conexion.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (org, carpeta)
        cursor.fetchall.return_value = []
        with patch("compartir.acceso.connections", {"default": conexion}):
            self.assertIsNone(acceso_usuario(usuario, archivo_id=archivo))
        consulta, parametros = cursor.execute.call_args.args
        self.assertEqual(parametros, [carpeta, org, usuario, archivo])
        self.assertIn("organizacion_id IS NOT DISTINCT FROM %s", consulta)
        self.assertIn("c.organizacion_id IS NOT DISTINCT FROM cadena.organizacion_id", consulta)

    def test_enlace_de_carpeta_rechaza_archivo_de_otra_organizacion(self):
        org, otra, carpeta = (uuid4() for _ in range(3))
        enlace = SimpleNamespace(archivo_id=None, carpeta_id=carpeta, recurso=Carpeta(organizacion_id=org))
        archivo = Archivo(organizacion_id=otra, carpeta_id=carpeta, en_papelera=False)
        self.assertFalse(dentro_del_enlace(enlace, archivo=archivo))

    def test_contenido_consulta_solo_hijos_del_mismo_ambito(self):
        carpeta = Carpeta(id=uuid4(), organizacion_id=uuid4())
        with (
            patch("compartir.views.Carpeta.objects") as carpetas,
            patch("compartir.views.Archivo.objects") as archivos,
        ):
            self.assertEqual(_contenido(carpeta), {"carpetas": [], "archivos": []})
            carpetas.filter.assert_called_once_with(
                padre_id=carpeta.pk, organizacion_id=carpeta.organizacion_id, en_papelera=False,
            )
            archivos.filter.assert_called_once_with(
                carpeta_id=carpeta.pk, organizacion_id=carpeta.organizacion_id, en_papelera=False,
            )

    def test_vista_previa_de_archivo_privado_requiere_concesion_para_miembro(self):
        org, actor = (uuid4() for _ in range(2))
        archivo = Archivo(id=uuid4(), organizacion_id=org, propietario_id=uuid4())
        cliente = APIClient()
        cliente.force_authenticate(Usuario(id=actor, is_active=True))
        ruta = f"/api/v1/archivos/{archivo.pk}/vista-previa/"
        with (
            patch("compartir.views.Archivo.objects") as archivos,
            patch("compartir.acceso.MiembroOrganizacion.objects") as miembros,
            patch("compartir.acceso.es_compartida", return_value=True),
            patch("compartir.views.acceso_usuario") as permiso,
            patch("compartir.views._url_temporal", return_value={"url_vista_previa": "https://example.test/"}) as firmar,
        ):
            archivos.filter.return_value.first.return_value = archivo
            miembros.filter.return_value.values_list.return_value.first.return_value = 2
            permiso.return_value = None
            self.assertEqual(cliente.get(ruta).status_code, 404)
            firmar.assert_not_called()
            permiso.return_value = Acceso(LECTURA, False, org)
            self.assertEqual(cliente.get(ruta).status_code, 200)
            firmar.assert_called_once_with(archivo, descargar=False)

    def test_patch_carpeta_respeta_escritura_aunque_el_rol_permite_operar(self):
        from contextlib import nullcontext
        from common.ambito import Ambito
        from storage.views import CarpetaViewSet

        org, actor = (uuid4() for _ in range(2))
        carpeta = Carpeta(id=uuid4(), organizacion_id=org, nombre="Anterior")
        cliente = APIClient()
        cliente.force_authenticate(Usuario(id=actor, is_active=True))
        ruta = f"/api/v1/carpetas/{carpeta.pk}/?organizacion_id={org}"
        with (
            patch("storage.views.resolver_organizacion", return_value=Ambito(org, 2, "COMPARTIDO")),
            patch("storage.views.RepositorioPapelera.transaccion", return_value=nullcontext()),
            patch.object(CarpetaViewSet, "get_object", return_value=carpeta),
            patch.object(CarpetaViewSet, "_nombre_unico", return_value=True),
            patch.object(CarpetaViewSet, "get_serializer", return_value=SimpleNamespace(data={"nombre": "Nuevo"})),
            patch("compartir.acceso.acceso_usuario") as permiso,
            patch.object(carpeta, "save") as guardar,
        ):
            permiso.return_value = Acceso(LECTURA, True, org)
            self.assertEqual(cliente.patch(ruta, {"nombre": "Nuevo"}, format="json").status_code, 403)
            guardar.assert_not_called()
            permiso.return_value = Acceso(ESCRITURA, True, org)
            self.assertEqual(cliente.patch(ruta, {"nombre": "Nuevo"}, format="json").status_code, 200)
            guardar.assert_called_once_with(update_fields=["nombre"])

    def test_archivo_propio_de_raiz_en_compartida_tiene_permiso_para_papelera(self):
        from storage.permisos_papelera import autorizar_envio
        from storage.repositorio_papelera import RepositorioPapelera

        org, actor = (uuid4() for _ in range(2))
        archivo = Archivo(id=uuid4(), organizacion_id=org, propietario_id=actor, carpeta_id=None)
        with patch("compartir.acceso.es_compartida", return_value=True):
            permisos = RepositorioPapelera().permisos(actor, archivo)
        self.assertEqual(permisos, [ESCRITURA])
        autorizar_envio(3, permisos)
        with self.assertRaises(PermissionDenied):
            autorizar_envio(2, permisos)

    def test_enlace_protegido_de_descarga_no_usa_permiso_de_solo_lectura_como_clave(self):
        from compartir.views import PublicoBase

        org, actor = (uuid4() for _ in range(2))
        recurso = Archivo(id=uuid4(), organizacion_id=org)
        solicitud = SimpleNamespace(user=Usuario(id=actor), headers={})
        with patch("compartir.views.acceso_usuario", return_value=Acceso(LECTURA, False, org)) as acceso:
            for permite_descarga in (True, False):
                enlace = SimpleNamespace(archivo_id=recurso.pk, carpeta_id=None, recurso=recurso,
                    contrasena_hash="fixture", rol=LECTURA, permite_descarga=permite_descarga)
                self.assertFalse(PublicoBase.verificado(solicitud, enlace))
            acceso.assert_not_called()
