"""Aceptación HTTP + SQL literal. JWT autorizado/S3/negocio son dobles explícitos.

Los rechazos de JWT se prueban sin force_authenticate en la suite de contrato.
Estas fixtures jamás se utilizan para certificar permisos de German o Railway.
"""

from datetime import timedelta
import hashlib
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from auth_workspaces.models import LogAuditoria, Usuario
from almacenamiento.adaptadores import ServiciosCompartidosValidados
from almacenamiento.configuracion_mantenimiento import PoliticaMantenimiento
from almacenamiento.mantenimiento import ServicioMantenimiento
from almacenamiento.models import EstadoSesion, IntentoPublicacion, SesionCarga
from almacenamiento.s3 import nueva_clave_final
from almacenamiento.persistencia import RepositorioCargas
from .fixtures_aceptacion import ProveedorEnsayo
from .test_inicio import InicioPersistenteTests
from .test_mantenimiento import BucketMantenimiento


class AceptacionHTTPTests(SimpleTestCase):
    databases = {"default"}
    firmador = InicioPersistenteTests.firmador

    def setUp(self):
        self.proveedor = ProveedorEnsayo()
        self.proveedor.sembrar()
        self.bucket = BucketMantenimiento()
        self.clientes = []
        self.firma = self.firmador()
        # Firma local real del SDK + operaciones de objetos exclusivamente dobles.
        self.bucket.firmar_descarga = self.firma.firmar_descarga
        self.parches = [
            patch("almacenamiento.views.servicios_compartidos", side_effect=lambda: ServiciosCompartidosValidados(self.proveedor)),
            patch("almacenamiento.views.cliente_firmador", return_value=self.firma),
            patch("almacenamiento.views.verificador_publicacion", return_value=self.bucket.verificar),
        ]
        for parche in self.parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.client = APIClient()
        self.actor(0)

    def actor(self, indice):
        self.client.force_authenticate(SimpleNamespace(pk=self.proveedor.actores[indice], is_authenticated=True))

    def iniciar(self, **cambios):
        return self.client.post("/api/v1/archivos/iniciar-carga/", {
            "nombre": "prueba-ñ.txt", "tipo_mime": "text/plain", "tamano_bytes": 5,
            "carpeta_id": str(self.proveedor.carpetas[0]), **cambios}, format="json")

    def confirmar(self, sesion):
        # Inicio necesita la firma; confirmación necesita el cliente de objetos.
        with patch("almacenamiento.views.cliente_firmador", return_value=self.bucket):
            return self.client.post(f"/api/v1/archivos/{sesion.archivo_id}/confirmar-carga/", {}, format="json")

    def cargar(self, **cambios):
        inicio = self.iniciar(**cambios)
        self.assertEqual(inicio.status_code, 201)
        sesion = SesionCarga.objects.get(archivo_id=inicio.data["data"]["archivo_id"])
        self.bucket.objetos[sesion.clave_temporal] = (b"12345", "text/plain")
        return sesion

    def estado_sql(self):
        with connection.cursor() as c:
            c.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [self.proveedor.organizaciones[0]])
            uso = c.fetchone()[0]
            c.execute("SELECT count(*) FROM archivos")
            archivos = c.fetchone()[0]
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=self.proveedor.organizaciones[0]):
            reserva = repo.bytes_pendientes(organizacion_id=self.proveedor.organizaciones[0])
        return uso, reserva, archivos

    def test_recorrido_http_completo_y_limpieza_conserva_final(self):
        sesion = self.cargar(tipo_mime="text/html")
        self.assertEqual(self.estado_sql(), (0, 5, 0))
        confirmacion = self.confirmar(sesion)
        self.assertEqual(confirmacion.status_code, 200)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, EstadoSesion.CONFIRMED)
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.assertEqual(sesion.checksum_sha256, hashlib.sha256(b"12345").hexdigest())
        self.assertEqual(self.confirmar(sesion).data, confirmacion.data)
        # Un lector del mismo ámbito puede descargar, aunque no cargar.
        self.actor(1)
        with patch("almacenamiento.views.cliente_firmador", return_value=self.bucket):
            descarga = self.client.get(f"/api/v1/archivos/{sesion.archivo_id}/descarga/")
        self.assertEqual(descarga.status_code, 200)
        archivo = self.proveedor.autorizar_descarga(solicitante_id=self.proveedor.actores[1], archivo_id=sesion.archivo_id)
        self.assertEqual(archivo.tipo_mime, "application/octet-stream")
        self.assertEqual(self.bucket.objetos[archivo.clave_final][0], b"12345")
        SesionCarga.objects.filter(pk=sesion.pk).update(creado_en=timezone.now()-timedelta(minutes=20), expira_en=timezone.now()-timedelta(minutes=1))
        mantenimiento = ServicioMantenimiento(servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=lambda: self.bucket, politica=PoliticaMantenimiento(margen_segundos=1))
        mantenimiento.ejecutar()
        self.assertNotIn(sesion.clave_temporal, self.bucket.objetos)
        self.assertIn(archivo.clave_final, self.bucket.objetos)
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.assertEqual(self.bucket.copias, 1)
        self.assertEqual(LogAuditoria.objects.filter(accion="CARGA_CONFIRMADA").count(), 1)

    def test_roles_cero_dos_tres_permitidos_y_lector_sin_efectos(self):
        for rol in (0, 2, 3):
            self.actor(rol)
            self.assertEqual(self.iniciar().status_code, 201)
        self.actor(1)
        respuesta = self.iniciar()
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.estado_sql(), (0, 15, 0))
        self.assertEqual(SesionCarga.objects.count(), 3)
        self.assertEqual(self.bucket.objetos, {})

    def test_carpeta_ajena_y_desconocida_mismo_rechazo(self):
        from uuid import uuid4
        ajena = self.iniciar(carpeta_id=str(self.proveedor.carpetas[1]))
        desconocida = self.iniciar(carpeta_id=str(uuid4()))
        self.assertEqual(ajena.status_code, 403)
        self.assertEqual(ajena.data, desconocida.data)
        self.assertEqual(self.estado_sql(), (0, 0, 0))
        self.assertFalse(LogAuditoria.objects.exists())

    def test_raiz_ambigua_y_personal_sin_ambito_no_reservan(self):
        with connection.cursor() as c:
            c.execute("INSERT INTO miembros_organizacion (organizacion_id,usuario_id,nivel_rol) VALUES (%s,%s,0)",
                      [self.proveedor.organizaciones[1], self.proveedor.actores[0]])
        self.assertEqual(self.iniciar(carpeta_id=None).status_code, 400)
        with connection.cursor() as c:
            c.execute("DELETE FROM miembros_organizacion WHERE usuario_id=%s", [self.proveedor.actores[0]])
        self.assertEqual(self.iniciar(carpeta_id=None).status_code, 403)
        self.assertEqual(self.estado_sql(), (0, 0, 0))

    def test_planes_ausente_vencido_inactivo_duplicado_rechazados(self):
        for modo in ("ausente", "vencido", "inactivo", "duplicado"):
            with self.subTest(modo=modo):
                self.proveedor.sembrar()
                with connection.cursor() as c:
                    if modo == "ausente":
                        c.execute("DELETE FROM suscripciones")
                    elif modo == "vencido":
                        c.execute("UPDATE suscripciones SET periodo_fin=CURRENT_TIMESTAMP-INTERVAL '1 second'")
                    elif modo == "inactivo":
                        c.execute("UPDATE planes SET esta_activo=false")
                    else:
                        c.execute("""INSERT INTO suscripciones (organizacion_id,plan_id,periodo_inicio,periodo_fin)
                            SELECT organizacion_id,plan_id,periodo_inicio,periodo_fin FROM suscripciones""")
                self.assertEqual(self.iniciar().status_code, 503)
                self.assertEqual(self.estado_sql(), (0, 0, 0))
                self.assertFalse(SesionCarga.objects.exists())

    def test_varios_actores_comparten_reserva_y_otra_org_independiente(self):
        self.assertEqual(self.iniciar(tamano_bytes=15).status_code, 201)
        self.actor(2)
        self.assertEqual(self.iniciar(tamano_bytes=6).status_code, 409)
        self.assertEqual(self.iniciar(tamano_bytes=5).status_code, 201)
        self.actor(4)
        self.assertEqual(self.iniciar(tamano_bytes=20, carpeta_id=str(self.proveedor.carpetas[1])).status_code, 201)
        self.assertEqual(self.estado_sql(), (0, 20, 0))

    def test_cero_bytes_en_cuota_exacta_y_ambito_bloqueado(self):
        self.assertEqual(self.iniciar(tamano_bytes=20).status_code, 201)
        self.assertEqual(self.iniciar(tamano_bytes=0).status_code, 201)
        with connection.cursor() as c:
            c.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=21 WHERE id=%s", [self.proveedor.organizaciones[0]])
        self.assertEqual(self.iniciar(tamano_bytes=0).status_code, 409)
        with connection.cursor() as c:
            c.execute("UPDATE organizaciones SET esta_activo=false WHERE id=%s", [self.proveedor.organizaciones[0]])
        self.assertEqual(self.iniciar(tamano_bytes=0).status_code, 503)
        self.assertEqual(SesionCarga.objects.count(), 2)

    def test_entradas_invalidas_http_no_dejan_filas(self):
        for cambio in ({"nombre": ""}, {"nombre": "x"*256}, {"nombre": "a\r\nb"},
                       {"tipo_mime": "no-mime"}, {"tamano_bytes": -1}, {"tamano_bytes": 1.5},
                       {"tamano_bytes": True}, {"tamano_bytes": "5"}, {"extra": True}):
            with self.subTest(cambio=cambio):
                self.assertEqual(self.iniciar(**cambio).status_code, 400)
        self.assertEqual(self.estado_sql(), (0, 0, 0))
        self.assertFalse(LogAuditoria.objects.exists())

    def test_header_idempotencia_no_deduplica_ni_se_exige(self):
        datos = {"nombre": "ensayo", "tipo_mime": "text/plain", "tamano_bytes": 5}
        primera = self.client.post("/api/v1/archivos/iniciar-carga/", datos, format="json", HTTP_IDEMPOTENCY_KEY="synthetic-repeat")
        segunda = self.client.post("/api/v1/archivos/iniciar-carga/", datos, format="json", HTTP_IDEMPOTENCY_KEY="synthetic-repeat")
        self.assertEqual((primera.status_code, segunda.status_code), (201, 201))
        self.assertNotEqual(primera.data["data"]["archivo_id"], segunda.data["data"]["archivo_id"])
        self.assertEqual(self.estado_sql(), (0, 10, 0))

    @override_settings(ALMACENAMIENTO_MAXIMO_ARCHIVO_BYTES=10)
    def test_limite_operativo_exacto_http_y_un_byte_superior(self):
        self.assertEqual(self.iniciar(tamano_bytes=10).status_code, 201)
        self.assertEqual(self.iniciar(tamano_bytes=11).status_code, 400)
        self.assertEqual(self.estado_sql(), (0, 10, 0))
        self.assertEqual(SesionCarga.objects.count(), 1)

    def test_put_mayor_rechazado_y_temporal_limpiado(self):
        sesion = self.cargar()
        self.bucket.objetos[sesion.clave_temporal] = (b"123456", "text/plain")
        self.assertEqual(self.confirmar(sesion).status_code, 400)
        self.assertEqual(self.estado_sql(), (0, 0, 0))
        self.assertEqual(self.bucket.copias, 0)
        SesionCarga.objects.filter(pk=sesion.pk).update(creado_en=timezone.now()-timedelta(minutes=20), expira_en=timezone.now()-timedelta(minutes=1))
        ServicioMantenimiento(servicios_factory=lambda: ServiciosCompartidosValidados(self.proveedor),
            cliente_factory=lambda: self.bucket, politica=PoliticaMantenimiento(margen_segundos=1)).ejecutar()
        self.assertNotIn(sesion.clave_temporal, self.bucket.objetos)
        self.assertEqual(self.estado_sql(), (0, 0, 0))

    def test_prepared_durable_visible_en_otro_proceso_y_recuperable(self):
        sesion = self.cargar()
        repo = RepositorioCargas()
        with repo.unidad_de_trabajo(organizacion_id=sesion.organizacion_id):
            repo.preparar_publicacion(archivo_id=sesion.archivo_id, solicitante_id=sesion.solicitante_id,
                clave_final=nueva_clave_final(sesion.archivo_id), etag_origen='"ensayo"')
        # Simula COPY concluido antes de que muera el proceso, sin llamar COPY.
        self.bucket.objetos[nueva_clave_final(sesion.archivo_id)] = (b"12345", "application/octet-stream")
        programa = """
import django, json, sys
django.setup()
from almacenamiento.models import IntentoPublicacion, SesionCarga
s = SesionCarga.objects.get(archivo_id=sys.argv[1])
i = IntentoPublicacion.objects.get(sesion=s)
print(json.dumps({'sesion': s.estado, 'ledger': i.estado, 'bytes': s.tamano_bytes}))
"""
        resultado = subprocess.run([sys.executable, "-c", programa, str(sesion.archivo_id)],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "almacenamiento.tests_persistencia.settings"},
            capture_output=True, text=True, timeout=10)
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(json.loads(resultado.stdout), {"sesion": "PENDING", "ledger": "PREPARED", "bytes": 5})
        self.assertEqual(self.confirmar(sesion).status_code, 200)
        self.assertEqual(IntentoPublicacion.objects.get(sesion=sesion).estado, "PUBLISHED")
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.assertEqual(self.bucket.copias, 0)

    def test_descarga_ajena_y_papelera_sin_url_ni_consumo_extra(self):
        sesion = self.cargar()
        self.assertEqual(self.confirmar(sesion).status_code, 200)
        self.actor(4)
        url = f"/api/v1/archivos/{sesion.archivo_id}/descarga/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.actor(0)
        with connection.cursor() as c:
            c.execute("UPDATE archivos SET en_papelera=true WHERE id=%s", [sesion.archivo_id])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn("url_descarga", str(respuesta.data))
        self.assertEqual(self.estado_sql(), (5, 0, 1))

    def test_trigger_sql_consumo_unico_y_doble_autoridad_revierte(self):
        with connection.cursor() as c:
            c.execute("""CREATE FUNCTION almacenamiento_tecnico.consumo_ensayo() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN UPDATE public.organizaciones
                SET almacenamiento_usado_bytes=almacenamiento_usado_bytes+NEW.tamano_bytes
                WHERE id=NEW.organizacion_id; RETURN NEW; END $$""")
            c.execute("""CREATE TRIGGER consumo_ensayo AFTER INSERT ON public.archivos
                FOR EACH ROW EXECUTE FUNCTION almacenamiento_tecnico.consumo_ensayo()""")
        def retirar():
            with connection.cursor() as c:
                c.execute("DROP TRIGGER consumo_ensayo ON public.archivos")
                c.execute("DROP FUNCTION almacenamiento_tecnico.consumo_ensayo()")
        self.addCleanup(retirar)
        self.proveedor.trigger = True
        sesion = self.cargar()
        self.assertEqual(self.confirmar(sesion).status_code, 200)
        self.assertEqual(self.confirmar(sesion).status_code, 200)
        self.assertEqual(self.estado_sql(), (5, 0, 1))
        self.proveedor.trigger = False  # Simula dos autoridades; debe revertir todo.
        otra = self.cargar()
        self.assertEqual(self.confirmar(otra).status_code, 500)
        self.assertEqual(self.estado_sql(), (5, 5, 1))
        otra.refresh_from_db()
        self.assertEqual(otra.estado, EstadoSesion.PENDING)


class CompatibilidadAuthTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        cache.clear()
        ProveedorEnsayo().sembrar()

    def test_mapping_fecha_de_auth_no_existe_en_referencia_literal(self):
        with connection.cursor() as c:
            columnas = {col.name for col in connection.introspection.get_table_description(c, "usuarios")}
        self.assertIn("creado_en", columnas)
        self.assertNotIn(Usuario._meta.get_field("date_joined").column, columnas)

    def test_registro_login_recuperacion_reproducen_bloqueo_sin_secretos(self):
        client = APIClient()
        datos = {"nombre_completo": "Ensayo", "correo_electronico": "auth@example.test",
                 "contrasena": "EnsayoPrueba8!", "palabra_secreta": "Recuerdo ficticio"}
        for ruta, cuerpo in (("registro", datos), ("login", {"correo": datos["correo_electronico"], "contrasena": datos["contrasena"]}),
                            ("recuperar-contrasena", {"correo": datos["correo_electronico"],
                             "palabra_secreta": datos["palabra_secreta"], "nueva_contrasena": "EnsayoPrueba9!",
                             "confirmar_contrasena": "EnsayoPrueba9!"})):
            with self.subTest(ruta=ruta):
                respuesta = client.post(f"/api/v1/auth/{ruta}/", cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 500)
                for privado in ("fecha_creacion", "SELECT", "EnsayoPrueba", "Recuerdo ficticio"):
                    self.assertNotIn(privado, str(respuesta.data))
        self.assertFalse(LogAuditoria.objects.exists())
