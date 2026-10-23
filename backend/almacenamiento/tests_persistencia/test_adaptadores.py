from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from django.db import transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.integracion import ArchivoVerificado, CuotaVigente, DestinoAutorizado
from almacenamiento.persistencia import IntegridadCarga, RepositorioCargas


class AdaptadoresTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.actor, self.org, self.carpeta, self.id = uuid4(), uuid4(), uuid4(), uuid4()
        self.destino = DestinoAutorizado(self.actor, self.org, self.carpeta)
        self.cuota = CuotaVigente(self.org, 1000, 100, timezone.now()+timedelta(days=1))
        self.archivo = ArchivoVerificado(self.id, self.actor, self.org, self.carpeta,
                                        "informe.pdf", "final/informe", 100, "application/pdf", None)
        repo = RepositorioCargas()
        self.proveedor = SimpleNamespace(using="default",
            resolver_destino=Mock(return_value=self.destino),
            bloquear_cuota=repo.unidad_de_trabajo,
            leer_cuota=Mock(return_value=self.cuota),
            registrar_archivo=Mock(), autorizar_descarga=Mock(return_value=self.archivo))
        self.puente = ServiciosCompartidosValidados(self.proveedor)

    def test_destino_y_raiz_correctos(self):
        self.assertEqual(self.puente.resolver_destino(solicitante_id=self.actor, carpeta_id=self.carpeta), self.destino)
        raiz = replace(self.destino, carpeta_id=None)
        self.proveedor.resolver_destino.return_value = raiz
        self.assertEqual(self.puente.resolver_destino(solicitante_id=self.actor, carpeta_id=None), raiz)

    def test_rechaza_destino_de_otro_actor_o_carpeta(self):
        for destino in (replace(self.destino, solicitante_id=uuid4()), replace(self.destino, carpeta_id=uuid4()),
                        replace(self.destino, organizacion_id="organizacion"), None):
            self.proveedor.resolver_destino.return_value = destino
            with self.assertRaises(IntegridadCarga):
                self.puente.resolver_destino(solicitante_id=self.actor, carpeta_id=self.carpeta)

    def test_denegacion_de_servicio_se_propaga(self):
        self.proveedor.resolver_destino.side_effect = PermissionDenied()
        with self.assertRaises(PermissionDenied):
            self.puente.resolver_destino(solicitante_id=self.actor, carpeta_id=self.carpeta)

    def test_alias_sql_debe_coincidir(self):
        self.proveedor.using = "remota"
        with self.assertRaises(IntegridadCarga):
            ServiciosCompartidosValidados(self.proveedor)

    def test_cuota_se_lee_bajo_bloqueo_del_ambito_correcto(self):
        with self.puente.bloquear_cuota(organizacion_id=self.org):
            self.assertEqual(self.puente.leer_cuota(organizacion_id=self.org), self.cuota)
            with self.assertRaises(RuntimeError):
                self.puente.leer_cuota(organizacion_id=uuid4())
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.puente.leer_cuota(organizacion_id=self.org)

    def test_bloqueo_de_servicio_sin_transaccion_se_rechaza(self):
        self.proveedor.bloquear_cuota = lambda **kwargs: nullcontext()
        with self.assertRaises(RuntimeError):
            with self.puente.bloquear_cuota(organizacion_id=self.org):
                pass

    def test_cuota_incoherente_y_periodo_vencido_rechazados(self):
        for cuota in (replace(self.cuota, organizacion_id=uuid4()), replace(self.cuota, limite_bytes=True),
                      replace(self.cuota, usado_bytes=-1), replace(self.cuota, periodo_fin=timezone.now()-timedelta(days=1)),
                      replace(self.cuota, periodo_fin=timezone.now().replace(tzinfo=None))):
            self.proveedor.leer_cuota.return_value = cuota
            with self.puente.bloquear_cuota(organizacion_id=self.org), self.assertRaises(IntegridadCarga):
                self.puente.leer_cuota(organizacion_id=self.org)

    def test_registro_requiere_transaccion_y_delega_sin_modelo_duplicado(self):
        with self.assertRaises(RuntimeError):
            self.puente.registrar_archivo(archivo=self.archivo)
        self.proveedor.registrar_archivo.assert_not_called()
        with transaction.atomic():
            self.puente.registrar_archivo(archivo=self.archivo)
        self.proveedor.registrar_archivo.assert_called_once_with(archivo=self.archivo)

    def test_descarga_usa_archivo_y_actor_del_servicio(self):
        self.assertEqual(self.puente.autorizar_descarga(solicitante_id=self.actor, archivo_id=self.id), self.archivo)
        for archivo in (replace(self.archivo, archivo_id=uuid4()), replace(self.archivo, solicitante_id=uuid4()),
                        replace(self.archivo, tamano_bytes=True)):
            self.proveedor.autorizar_descarga.return_value = archivo
            with self.assertRaises(IntegridadCarga):
                self.puente.autorizar_descarga(solicitante_id=self.actor, archivo_id=self.id)

    def test_descarga_rechaza_identidades_invalidas_antes_de_consultar_proveedor(self):
        for actor, archivo in ((str(self.actor), self.id), (self.actor, str(self.id)),
                               (None, self.id), (self.actor, None), (True, self.id)):
            with self.subTest(actor=actor, archivo=archivo), self.assertRaises(IntegridadCarga):
                self.puente.autorizar_descarga(solicitante_id=actor, archivo_id=archivo)
        self.proveedor.autorizar_descarga.assert_not_called()

    def test_denegacion_actual_de_descarga_y_registro_se_propaga_sin_exito(self):
        # No reutilizar un resultado antes autorizado cuando el proveedor deniega.
        self.puente.autorizar_descarga(solicitante_id=self.actor, archivo_id=self.id)
        self.proveedor.autorizar_descarga.side_effect = PermissionDenied()
        with self.assertRaises(PermissionDenied):
            self.puente.autorizar_descarga(solicitante_id=self.actor, archivo_id=self.id)
        self.proveedor.registrar_archivo.side_effect = PermissionDenied()
        with transaction.atomic(), self.assertRaises(PermissionDenied):
            self.puente.registrar_archivo(archivo=self.archivo)

    def test_registro_rechaza_clave_incompatible_antes_de_delegar(self):
        for cambios in ({"clave_final": "x" * 256}, {"clave_final": "final/\n"},
                        {"checksum_sha256": "A" * 64}, {"checksum_sha256": "a" * 63}):
            with self.subTest(cambios=cambios), transaction.atomic(), self.assertRaises(ValueError):
                self.puente.registrar_archivo(archivo=replace(self.archivo, **cambios))
        self.proveedor.registrar_archivo.assert_not_called()

    def test_registro_acepta_clave_publicable_limite_y_checksum_sin_modificarlos(self):
        archivo = replace(self.archivo, clave_final="x" * 255, checksum_sha256="a" * 64)
        with transaction.atomic():
            self.puente.registrar_archivo(archivo=archivo)
        self.proveedor.registrar_archivo.assert_called_once_with(archivo=archivo)
