"""Fase 04 con PostgreSQL aislado, proveedor sintético y firmas offline.

El SQL de negocio de fixtures no es un proveedor desplegable ni se ejecuta en la
base compartida. No sube objetos, no lee .env y no conecta con Railway.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db import OperationalError, connection, connections, transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.test import APIClient

from auth_workspaces.models import LogAuditoria
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.inicio import ServicioInicioCargas
from almacenamiento.integracion import CuotaVigente, DestinoAutorizado
from almacenamiento.models import EstadoSesion, SesionCarga
from almacenamiento.persistencia import RepositorioCargas
from almacenamiento.s3 import ClienteS3, ErrorS3


class InicioPersistenteTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.actor, self.otro_actor, self.org, self.otra_org, self.carpeta = [uuid4() for _ in range(5)]
        self.limite = 100
        self.fin = timezone.now() + timedelta(days=1)
        self.clientes = []
        self.fabrica = Mock(side_effect=self.firmador)
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE organizaciones, usuarios, planes CASCADE")
            for actor in (self.actor, self.otro_actor):
                cursor.execute("""INSERT INTO usuarios
                    (id,nombre_completo,correo_electronico,contrasena_hash,palabra_secreta_hash)
                    VALUES (%s,'Persona sintética',%s,'hash-sintetico','hash-sintetico')""",
                               [actor, f"{actor}@example.test"])
            for org in (self.org, self.otra_org):
                cursor.execute("""INSERT INTO organizaciones
                    (id,nombre,slug,almacenamiento_usado_bytes) VALUES (%s,'Test',%s,80)""", [org, str(org)])
            cursor.execute("""INSERT INTO carpetas (id,organizacion_id,propietario_id,nombre)
                VALUES (%s,%s,%s,'Test')""", [self.carpeta, self.org, self.actor])
        self.repo_proveedor = RepositorioCargas()
        self.proveedor = SimpleNamespace(
            using="default", resolver_destino=Mock(side_effect=self.destino),
            bloquear_cuota=self.repo_proveedor.unidad_de_trabajo,
            leer_cuota=Mock(side_effect=self.cuota),
        )

    def destino(self, *, solicitante_id, carpeta_id):
        return DestinoAutorizado(solicitante_id, self.org, carpeta_id)

    def cuota(self, *, organizacion_id):
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [organizacion_id])
            usado = cursor.fetchone()[0]
        return CuotaVigente(organizacion_id, self.limite, usado, self.fin)

    def firmador(self):
        cliente = ClienteS3(ConfiguracionS3(
            "railway", "https://s3.example.test", "auto", "bucket-sintetico",
            "synthetic-access", "synthetic-secret"))
        cliente.firmar_put = Mock(wraps=cliente.firmar_put)
        self.clientes.append(cliente)
        return cliente

    def servicio(self, **kwargs):
        return ServicioInicioCargas(
            servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            firmador_factory=self.fabrica, **kwargs)

    def iniciar(self, servicio=None, **cambios):
        datos = {"nombre": "ensayo.txt", "tipo_mime": "text/plain",
                 "tamano_bytes": 5, "carpeta_id": str(self.carpeta)}
        datos.update(cambios)
        return (servicio or self.servicio()).iniciar(solicitante_id=self.actor, datos=datos)

    def reservar_anterior(self, *, tamano=15, vencida=False, intento=False):
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.org):
            sesion = repo.crear_sesion(
                archivo_id=uuid4(), destino=DestinoAutorizado(self.actor, self.org, self.carpeta),
                nombre="anterior.txt", tipo_mime="text/plain", tamano_bytes=tamano,
                clave_temporal=f"cloudvault/dani/temporales/{uuid4()}",
                expira_en=timezone.now() + timedelta(minutes=10))
            if intento:
                repo.preparar_publicacion(archivo_id=sesion.archivo_id, solicitante_id=self.actor,
                                          clave_final=f"cloudvault/dani/publicaciones/{uuid4()}",
                                          etag_origen='"sintetico"')
        if vencida:
            SesionCarga.objects.filter(pk=sesion.pk).update(
                creado_en=timezone.now() - timedelta(minutes=5),
                expira_en=timezone.now() - timedelta(minutes=1))
        return sesion

    def test_respuesta_durable_sesion_auditoria_y_sin_archivo_ni_consumo(self):
        salida = self.iniciar()
        sesion = SesionCarga.objects.get(archivo_id=salida["data"]["archivo_id"])
        self.assertEqual(sesion.estado, EstadoSesion.PENDING)
        self.assertEqual(sesion.tamano_bytes, 5)
        self.assertEqual(sesion.solicitante_id, self.actor)
        self.assertEqual(sesion.organizacion_id, self.org)
        self.assertTrue(sesion.clave_temporal.startswith("cloudvault/dani/temporales/"))
        self.assertEqual(salida["data"]["metodo"], "PUT")
        self.assertEqual(salida["data"]["encabezados"], {"Content-Type": "text/plain"})
        self.assertEqual(salida["data"]["expira_en"], sesion.expira_en.isoformat().replace("+00:00", "Z"))
        self.assertEqual(LogAuditoria.objects.count(), 1)
        self.assertNotIn(salida["data"]["url_subida"], str(LogAuditoria.objects.get().detalles))
        self.assertFalse(connection.in_atomic_block)
        self.assertEqual(self.cuota(organizacion_id=self.org).usado_bytes, 80)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM archivos")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_sesion_ya_existe_al_firmar(self):
        cliente = self.firmador()
        original = cliente.firmar_put
        def firmar(clave, mime, **kwargs):
            self.assertEqual(SesionCarga.objects.filter(clave_temporal=clave).count(), 1)
            self.assertTrue(connection.in_atomic_block)
            return original(clave, mime, **kwargs)
        cliente.firmar_put = Mock(side_effect=firmar)
        self.fabrica.side_effect = None
        self.fabrica.return_value = cliente
        self.iniciar()

    def test_limite_exacto_y_exceso_no_firma(self):
        self.reservar_anterior(tamano=15)
        self.iniciar(tamano_bytes=5)
        with self.assertRaises(ErrorCarga) as error:
            self.iniciar(tamano_bytes=1)
        self.assertEqual(error.exception.codigo, CodigoError.CUOTA_EXCEDIDA)
        self.assertEqual(SesionCarga.objects.count(), 2)
        self.assertEqual(LogAuditoria.objects.count(), 1)
        self.clientes[-1].firmar_put.assert_not_called()

    def test_reservas_vencidas_no_consumen_y_se_marcan_sin_borrar(self):
        anterior = self.reservar_anterior(tamano=90, vencida=True)
        self.iniciar(tamano_bytes=20)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, EstadoSesion.EXPIRED)
        self.assertEqual(SesionCarga.objects.count(), 2)

    def test_vencida_con_intento_queda_para_reconciliacion(self):
        anterior = self.reservar_anterior(tamano=90, vencida=True, intento=True)
        self.iniciar(tamano_bytes=20)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, EstadoSesion.PENDING)

    def test_vacio_y_raiz_autorizada(self):
        salida = self.iniciar(tamano_bytes=0, carpeta_id=None)
        sesion = SesionCarga.objects.get(archivo_id=salida["data"]["archivo_id"])
        self.assertIsNone(sesion.carpeta_id)
        self.assertEqual(sesion.tamano_bytes, 0)

    def test_permiso_denegado_no_reserva_ni_construye_firmador(self):
        self.proveedor.resolver_destino.side_effect = PermissionDenied()
        with self.assertRaises(PermissionDenied):
            self.iniciar()
        self.assertEqual(SesionCarga.objects.count(), 0)
        self.fabrica.assert_not_called()

    def test_destino_cambia_bajo_bloqueo_y_no_reserva(self):
        inicial = DestinoAutorizado(self.actor, self.org, self.carpeta)
        self.proveedor.resolver_destino.side_effect = [inicial, replace(inicial, organizacion_id=self.otra_org)]
        with self.assertRaises(ErrorCarga) as error:
            self.iniciar()
        self.assertEqual(error.exception.codigo, CodigoError.SIN_PERMISO)
        self.assertEqual(SesionCarga.objects.count(), 0)
        self.clientes[-1].firmar_put.assert_not_called()

    def test_plan_vencido_rechazado_y_firma_no_supera_periodo(self):
        self.fin = timezone.now() - timedelta(seconds=1)
        with self.assertRaises(ValueError):
            self.iniciar()
        self.assertEqual(SesionCarga.objects.count(), 0)
        self.fin = timezone.now() + timedelta(seconds=30)
        salida = self.iniciar()
        sesion = SesionCarga.objects.get(archivo_id=salida["data"]["archivo_id"])
        self.assertLessEqual(sesion.expira_en, self.fin)

    def test_firma_fallida_revierte_reserva_y_auditoria(self):
        cliente = self.firmador()
        cliente.firmar_put.side_effect = ErrorS3()
        self.fabrica.side_effect = None
        self.fabrica.return_value = cliente
        with self.assertRaises(ErrorS3):
            self.iniciar()
        self.assertEqual(SesionCarga.objects.count(), 0)
        self.assertEqual(LogAuditoria.objects.count(), 0)

    def test_auditoria_obligatoria_fallida_revierte_reserva(self):
        servicio = self.servicio(auditoria=Mock(side_effect=OperationalError("synthetic-private-error")))
        with self.assertRaises(OperationalError):
            self.iniciar(servicio)
        self.assertEqual(SesionCarga.objects.count(), 0)
        self.assertEqual(LogAuditoria.objects.count(), 0)

    def test_commit_fallido_no_devuelve_exito(self):
        with patch.object(connection, "commit", side_effect=OperationalError("synthetic-commit-error")):
            with self.assertRaises(OperationalError):
                self.iniciar()
        self.assertEqual(SesionCarga.objects.count(), 0)

    def test_limite_persistente_429_en_otro_servicio(self):
        self.iniciar(self.servicio(limite_inicios=1))
        with self.assertRaises(Throttled):
            self.iniciar(self.servicio(limite_inicios=1))
        self.assertEqual(SesionCarga.objects.count(), 1)
        self.clientes[-1].firmar_put.assert_not_called()

    def test_respuesta_perdida_y_reintento_no_prometen_idempotencia(self):
        primera = self.iniciar()
        # La primera respuesta podría perderse tras commit; otro inicio crea otra reserva.
        segunda = self.iniciar(self.servicio())
        self.assertNotEqual(primera["data"]["archivo_id"], segunda["data"]["archivo_id"])
        self.assertEqual(SesionCarga.objects.count(), 2)
        self.assertEqual(LogAuditoria.objects.count(), 2)
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.org):
            self.assertEqual(repo.bytes_pendientes(organizacion_id=self.org), 10)

    def test_no_devuelve_sesion_de_transaccion_exterior_sin_commit(self):
        with transaction.atomic(), self.assertRaises(RuntimeError):
            self.iniciar()
        self.assertEqual(SesionCarga.objects.count(), 0)

    def test_endpoint_201_con_postgresql_y_firma_offline(self):
        cliente = APIClient()
        cliente.force_authenticate(SimpleNamespace(pk=self.actor, is_authenticated=True))
        with patch("almacenamiento.views.servicios_compartidos",
                   side_effect=lambda: ServiciosCompartidosValidados(self.proveedor)), \
             patch("almacenamiento.views.cliente_firmador", side_effect=self.firmador):
            respuesta = cliente.post("/api/v1/archivos/iniciar-carga/", {
                "nombre": "ensayo.txt", "tamano_bytes": 5, "tipo_mime": "text/plain",
                "carpeta_id": str(self.carpeta)}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(SesionCarga.objects.filter(archivo_id=respuesta.data["data"]["archivo_id"]).exists())

    def test_dos_conexiones_no_reservan_el_mismo_ultimo_espacio(self):
        barrera = Barrier(2)
        def iniciar(actor):
            connections.close_all()
            try:
                barrera.wait(timeout=5)
                salida = self.servicio().iniciar(solicitante_id=actor, datos={
                    "nombre": "ensayo.txt", "tamano_bytes": 15, "tipo_mime": "text/plain",
                    "carpeta_id": str(self.carpeta)})
                return 201, salida["data"]["archivo_id"]
            except ErrorCarga as exc:
                return exc.status_code, exc.codigo
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(iniciar, (self.actor, self.otro_actor)))
        self.assertEqual(sorted(r[0] for r in resultados), [201, 409])
        self.assertEqual(SesionCarga.objects.count(), 1)
        self.assertEqual(LogAuditoria.objects.count(), 1)

    def test_downgrade_bloqueado_se_lee_despues_del_cambio(self):
        # Escritor/lector externos sintéticos; cambios reales en SQL desechable.
        from threading import Event
        import time
        tomado, liberar, listo = Event(), Event(), Event()
        pid_carga = []
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO planes (nombre,limite_almacenamiento_bytes) VALUES ('Plan de prueba',100) RETURNING id")
            plan = cursor.fetchone()[0]
        def leer_plan(*, organizacion_id):
            cuota = self.cuota(organizacion_id=organizacion_id)
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT limite_almacenamiento_bytes FROM planes WHERE id=%s", [plan])
                return replace(cuota, limite_bytes=cursor.fetchone()[0])
        self.proveedor.leer_cuota.side_effect = leer_plan
        def bajar_plan():
            connections.close_all()
            try:
                with RepositorioCargas().unidad_de_trabajo(organizacion_id=self.org):
                    with connections["default"].cursor() as cursor:
                        cursor.execute("UPDATE planes SET limite_almacenamiento_bytes=80 WHERE id=%s", [plan])
                    tomado.set()
                    if not liberar.wait(timeout=5):
                        raise RuntimeError("Tiempo de prueba agotado")
            finally:
                connections.close_all()
        def carga():
            connections.close_all()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_carga.append(cursor.fetchone()[0])
                listo.set()
                self.iniciar(tamano_bytes=1)
            except ErrorCarga as exc:
                return exc.codigo
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            cambio = pool.submit(bajar_plan)
            self.assertTrue(tomado.wait(timeout=5))
            peticion = pool.submit(carga)
            try:
                self.assertTrue(listo.wait(timeout=5))
                limite = time.monotonic() + 5
                esperando = False
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted)", pid_carga)
                        esperando = cursor.fetchone()[0]
                    if esperando:
                        break
                    time.sleep(0.01)
                self.assertTrue(esperando, "La carga debe esperar el bloqueo del cambio de plan")
            finally:
                liberar.set()
            cambio.result(timeout=5)
            self.assertEqual(peticion.result(timeout=5), CodigoError.CUOTA_EXCEDIDA)
        self.assertEqual(SesionCarga.objects.count(), 0)
