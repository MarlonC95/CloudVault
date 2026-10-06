"""PostgreSQL real; SQL de negocio aquí es únicamente fixture/doble de prueba."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
import subprocess
import sys
from unittest.mock import Mock
from threading import Event
from uuid import uuid4

from django.db import IntegrityError, connection, connections, transaction
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from almacenamiento.esquema import inspeccionar_esquema
from almacenamiento.integracion import DestinoAutorizado
from almacenamiento.models import EstadoPublicacion, EstadoSesion, IntentoPublicacion, SesionCarga
from almacenamiento.persistencia import EstadoIncompatible, IntegridadCarga, RepositorioCargas, clave_bloqueo_cuota


class PersistenciaTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.repo = RepositorioCargas()
        self.actor, self.otro_actor = uuid4(), uuid4()
        self.org, self.otra_org = uuid4(), uuid4()
        self.carpeta = uuid4()
        self.archivo = uuid4()
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE organizaciones, usuarios, planes CASCADE")
            for actor in (self.actor, self.otro_actor):
                cursor.execute("""INSERT INTO usuarios (id,nombre_completo,correo_electronico,contrasena_hash,palabra_secreta_hash)
                    VALUES (%s,'Persona de prueba',%s,'hash-sintetico','hash-sintetico')""", [actor, f"{actor}@example.test"])
            for org in (self.org, self.otra_org):
                cursor.execute("INSERT INTO organizaciones (id,nombre,slug) VALUES (%s,'Prueba',%s)", [org, str(org)])
            cursor.execute("INSERT INTO carpetas (id,organizacion_id,propietario_id,nombre) VALUES (%s,%s,%s,'Carpeta')",
                           [self.carpeta, self.org, self.actor])
        self.destino = DestinoAutorizado(self.actor, self.org, self.carpeta)

    def crear(self, **cambios):
        datos = dict(archivo_id=self.archivo, destino=self.destino, nombre="informe.pdf",
                     tipo_mime="application/pdf", tamano_bytes=100,
                     clave_temporal=f"tmp/{uuid4()}", expira_en=timezone.now() + timedelta(minutes=10))
        datos.update(cambios)
        with self.repo.unidad_de_trabajo(organizacion_id=datos["destino"].organizacion_id):
            return self.repo.crear_sesion(**datos)

    def preparar(self, **cambios):
        datos = dict(archivo_id=self.archivo, solicitante_id=self.actor,
                     clave_final=f"final/{self.archivo}", etag_origen='"origen"', checksum_origen="a" * 64)
        datos.update(cambios)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            return self.repo.preparar_publicacion(**datos)

    def publicar(self):
        self.preparar()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            return self.repo.marcar_publicado(archivo_id=self.archivo, solicitante_id=self.actor, etag_final='"final"')

    def registrar_doble(self, *, sesion, intento, using):
        # Simula el servicio de German; jamás se instala como adaptador real.
        with connections[using].cursor() as cursor:
            cursor.execute("""INSERT INTO archivos
                (id,organizacion_id,carpeta_id,propietario_id,nombre_original,clave_s3,tamano_bytes,tipo_mime,checksum_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [sesion.archivo_id, sesion.organizacion_id, sesion.carpeta_id, sesion.solicitante_id,
                 sesion.nombre, intento.clave_final, sesion.tamano_bytes, sesion.tipo_mime, intento.checksum_origen])
            # Una autoridad sintética de cuota; el SQL recibido NO tiene este trigger.
            cursor.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=almacenamiento_usado_bytes+%s WHERE id=%s",
                           [sesion.tamano_bytes, sesion.organizacion_id])

    def test_mapping_y_dependencias_diagnosticadas(self):
        informe = inspeccionar_esquema()
        self.assertTrue(informe.compatible, informe.problemas)
        self.assertEqual(len(informe.advertencias), 2)
        self.assertFalse(informe.triggers_archivos)
        for modelo in (SesionCarga, IntentoPublicacion):
            self.assertFalse(modelo._meta.managed)
            with connection.cursor() as cursor:
                descripcion = connection.introspection.get_table_description(cursor, modelo._meta.db_table)
            self.assertEqual({c.name for c in descripcion}, {c.column for c in modelo._meta.local_fields})
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
            self.assertEqual(cursor.fetchone()[0], 13)
            cursor.execute("""SELECT table_name, column_name, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema='public' AND
                ((table_name='sesiones_carga' AND column_name='clave_temporal') OR
                 (table_name='intentos_publicacion' AND column_name='clave_final'))""")
            longitudes = {(tabla, campo): limite for tabla, campo, limite in cursor.fetchall()}
        for modelo, campo in ((SesionCarga, "clave_temporal"), (IntentoPublicacion, "clave_final")):
            self.assertEqual(modelo._meta.get_field(campo).max_length,
                             longitudes[(modelo._meta.db_table, campo)])

    def test_default_uuid_estados_y_fechas_generados_por_sql(self):
        sesion = self.crear()
        sesion.refresh_from_db()
        self.assertIsNotNone(sesion.id)
        self.assertEqual(sesion.estado, EstadoSesion.PENDING)
        self.assertIsNone(sesion.checksum_sha256)
        self.assertLess(sesion.creado_en, sesion.expira_en)
        intento = self.preparar()
        intento.refresh_from_db()
        self.assertEqual(intento.estado, EstadoPublicacion.PREPARED)
        self.assertIsNotNone(intento.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM archivos")
            self.assertEqual(cursor.fetchone()[0], 0)  # UUID reservado sin crear metadatos

    def test_lectura_limitada_al_solicitante(self):
        self.crear()
        self.assertEqual(self.repo.recuperar_sesion(archivo_id=self.archivo, solicitante_id=self.actor).archivo_id, self.archivo)
        with self.assertRaises(SesionCarga.DoesNotExist):
            self.repo.recuperar_sesion(archivo_id=self.archivo, solicitante_id=self.otro_actor)

    def test_no_escribir_fuera_de_unidad_de_trabajo(self):
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                self.repo.preparar_publicacion(archivo_id=self.archivo, solicitante_id=self.actor,
                                              clave_final="final/x", etag_origen="origen")
        with self.assertRaises(RuntimeError):
            self.repo.bytes_pendientes(organizacion_id=self.org)

    def test_ambito_y_unidades_anidadas_rechazados(self):
        self.crear()
        with self.repo.unidad_de_trabajo(organizacion_id=self.otra_org):
            with self.assertRaises(SesionCarga.DoesNotExist):
                self.repo.preparar_publicacion(archivo_id=self.archivo, solicitante_id=self.actor,
                                              clave_final="final/x", etag_origen="origen")
            with self.assertRaises(RuntimeError):
                with self.repo.unidad_de_trabajo(organizacion_id=self.org):
                    pass

    def test_validacion_previa_no_persiste_datos_invalidos(self):
        for cambios in ({"tamano_bytes": True}, {"tamano_bytes": -1}, {"nombre": "../x"}, {"tipo_mime": "invalid"}):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                self.crear(**cambios)
        for cambios in ({"expira_en": timezone.now() - timedelta(seconds=1)}, {"clave_temporal": "x" * 1025}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                self.crear(**cambios)
        self.assertEqual(SesionCarga.objects.count(), 0)

    def test_constraints_sql_rechazan_escritura_directa_invalida(self):
        sesion = self.crear()
        for cambios in ({"tamano_bytes": -1}, {"estado": "INVALID"}, {"checksum_sha256": "ABC"},
                        {"expira_en": sesion.creado_en}, {"solicitante_id": uuid4()}, {"organizacion_id": uuid4()},
                        {"carpeta_id": uuid4()}):
            with self.subTest(cambios=cambios), self.assertRaises(IntegrityError), transaction.atomic():
                SesionCarga.objects.filter(pk=sesion.pk).update(**cambios)

    def test_clave_temporal_en_limite_sql_y_rechazo_sin_persistir(self):
        with self.assertRaises(ValueError):
            self.crear(clave_temporal="t" * 1025)
        self.assertEqual(SesionCarga.objects.count(), 0)
        sesion = self.crear(clave_temporal="t" * 1024)
        sesion.refresh_from_db()
        self.assertEqual(sesion.clave_temporal, "t" * 1024)

    def test_clave_final_publicable_en_limite_y_metadatos_reales_de_prueba(self):
        self.crear()
        with self.assertRaises(ValueError):
            self.preparar(clave_final="f" * 256)
        self.assertEqual(IntentoPublicacion.objects.count(), 0)
        self.preparar(clave_final="f" * 255)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            self.repo.marcar_publicado(archivo_id=self.archivo, solicitante_id=self.actor,
                                      etag_final='"final"')
            self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor,
                                            registrar_metadatos=self.registrar_doble)
        with connection.cursor() as cursor:
            cursor.execute("SELECT clave_s3 FROM archivos WHERE id=%s", [self.archivo])
            self.assertEqual(cursor.fetchone()[0], "f" * 255)

    def test_unicidad_archivo_y_clave_temporal(self):
        sesion = self.crear()
        with self.assertRaises(IntegrityError):
            self.crear()
        with self.assertRaises(IntegrityError):
            self.crear(archivo_id=uuid4(), clave_temporal=sesion.clave_temporal)
        self.assertEqual(SesionCarga.objects.count(), 1)

    def test_reservas_solo_pendientes_vigentes_de_organizacion(self):
        sesion = self.crear()
        cancelada = self.crear(archivo_id=uuid4(), tamano_bytes=500)
        SesionCarga.objects.filter(pk=cancelada.pk).update(estado=EstadoSesion.CANCELED)
        self.crear(archivo_id=uuid4(), tamano_bytes=700, destino=DestinoAutorizado(self.actor, self.otra_org, None))
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            self.assertEqual(self.repo.bytes_pendientes(organizacion_id=self.org), 100)
            self.assertEqual(self.repo.bytes_pendientes(organizacion_id=self.org,
                ahora=sesion.expira_en - timedelta(microseconds=1)), 100)
            self.assertEqual(self.repo.bytes_pendientes(organizacion_id=self.org,
                ahora=sesion.expira_en), 0)
            self.assertEqual(self.repo.bytes_pendientes(organizacion_id=self.org, ahora=timezone.now() + timedelta(days=1)), 0)

    def test_triggers_actualizan_timestamp_en_ambas_tablas(self):
        sesion = self.crear()
        sesion.refresh_from_db()
        anterior_sesion = sesion.actualizado_en
        intento = self.preparar()
        intento.refresh_from_db()
        anterior_intento = intento.actualizado_en
        self.publicar()
        SesionCarga.objects.filter(pk=sesion.pk).update(etag="valor")
        sesion.refresh_from_db()
        intento.refresh_from_db()
        self.assertGreater(sesion.actualizado_en, anterior_sesion)
        self.assertGreater(intento.actualizado_en, anterior_intento)

    def test_intento_idempotente_rechaza_otro_contenido(self):
        self.crear()
        primero = self.preparar()
        self.assertEqual(self.preparar().pk, primero.pk)
        for cambios in ({"etag_origen": "otro"}, {"version_origen": "v2"}, {"checksum_origen": "b" * 64},
                        {"clave_final": "otro/final"}):
            with self.subTest(cambios=cambios), self.assertRaises(EstadoIncompatible):
                self.preparar(**cambios)
        for cambios in ({"clave_final": "x" * 256}, {"checksum_origen": "A" * 64}, {"etag_origen": "x\n"}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                self.preparar(**cambios)
        self.assertEqual(IntentoPublicacion.objects.count(), 1)

    def test_resultado_publicado_idempotente(self):
        self.crear()
        primero = self.publicar()
        self.assertEqual(self.publicar().pk, primero.pk)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.marcar_publicado(archivo_id=self.archivo, solicitante_id=self.actor, etag_final="otro")

    def test_no_confirmar_sin_publicacion_verificada(self):
        self.crear()
        self.preparar()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor, registrar_metadatos=self.registrar_doble)

    def test_confirmacion_atomica_y_repeticion_sin_duplicar_metadatos_o_uso(self):
        self.crear()
        self.publicar()
        llamadas = []
        def callback(**datos):
            llamadas.append(True)
            self.registrar_doble(**datos)
        resultados = []
        for _ in range(2):
            with self.repo.unidad_de_trabajo(organizacion_id=self.org):
                resultados.append(self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor,
                                                                   registrar_metadatos=callback))
                self.assertEqual(self.repo.bytes_pendientes(organizacion_id=self.org), 0)
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(len(llamadas), 1)
        self.assertEqual(set(resultados[0]["data"]), {"id", "nombre", "es_nuevo", "en_papelera"})
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM archivos")
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [self.org])
            self.assertEqual(cursor.fetchone()[0], 100)

    def test_fallo_metadatos_revierte_incluso_si_llamador_captura_error(self):
        self.crear()
        self.publicar()
        def fallar(**datos):
            self.registrar_doble(**datos)
            raise RuntimeError("Fallo sintético después del INSERT")
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            with self.assertRaises(RuntimeError):
                self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor, registrar_metadatos=fallar)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM archivos")
            self.assertEqual(cursor.fetchone()[0], 0)
            cursor.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [self.org])
            self.assertEqual(cursor.fetchone()[0], 0)
        sesion = self.repo.recuperar_sesion(archivo_id=self.archivo, solicitante_id=self.actor)
        self.assertEqual(sesion.estado, EstadoSesion.PENDING)
        self.assertIsNone(sesion.resultado_confirmacion)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor, registrar_metadatos=self.registrar_doble)

    def test_confirmacion_corrupta_no_simula_exito(self):
        sesion = self.crear()
        SesionCarga.objects.filter(pk=sesion.pk).update(estado=EstadoSesion.CONFIRMED)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(IntegridadCarga):
            self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor, registrar_metadatos=self.registrar_doble)

    def test_otro_actor_o_ambito_no_confirma_ni_modifica_sesion_publicada(self):
        sesion = self.crear()
        intento = self.publicar()
        callback = Mock()
        for actor, org in ((self.otro_actor, self.org), (self.actor, self.otra_org)):
            with self.subTest(actor=actor, org=org):
                with self.repo.unidad_de_trabajo(organizacion_id=org), self.assertRaises(SesionCarga.DoesNotExist):
                    self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=actor,
                                                    registrar_metadatos=callback)
        callback.assert_not_called()
        sesion.refresh_from_db()
        intento.refresh_from_db()
        self.assertEqual(sesion.estado, EstadoSesion.PENDING)
        self.assertEqual(intento.estado, EstadoPublicacion.PUBLISHED)
        self.assertIsNone(sesion.resultado_confirmacion)

    def test_sesion_vencida_no_confirma_y_conserva_intento_para_reconciliar(self):
        sesion = self.crear()
        intento = self.publicar()
        SesionCarga.objects.filter(pk=sesion.pk).update(
            creado_en=timezone.now()-timedelta(days=2), expira_en=timezone.now()-timedelta(days=1))
        callback = Mock()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor,
                                            registrar_metadatos=callback)
        callback.assert_not_called()
        intento.refresh_from_db()
        self.assertEqual(intento.estado, EstadoPublicacion.PUBLISHED)
        self.assertTrue(SesionCarga.objects.filter(pk=sesion.pk).exists())

    def test_confirmacion_no_persiste_datos_extra_retornados_por_callback(self):
        sesion = self.crear()
        self.publicar()
        secreto = "synthetic-callback-secret"

        def callback(**datos):
            self.registrar_doble(**datos)
            return {"token": secreto, "url_firmada": "https://example.test/?Signature=" + secreto}

        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            respuesta = self.repo.confirmar_atomicamente(archivo_id=self.archivo, solicitante_id=self.actor,
                                                        registrar_metadatos=callback)
        sesion.refresh_from_db()
        self.assertEqual(sesion.resultado_confirmacion, respuesta)
        self.assertEqual(set(respuesta["data"]), {"id", "nombre", "es_nuevo", "en_papelera"})
        self.assertNotIn(secreto, json.dumps(sesion.resultado_confirmacion))

    def test_cancelacion_durable_y_terminal_sin_reabrir(self):
        self.crear()
        for _ in range(2):
            with self.repo.unidad_de_trabajo(organizacion_id=self.org):
                self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.CANCELED)
        with self.assertRaises(EstadoIncompatible):
            self.preparar()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.EXPIRED)

    def test_no_liberar_sesion_con_intento_sin_reconciliar(self):
        self.crear()
        self.preparar()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.CANCELED)
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            self.repo.abandonar_publicacion(archivo_id=self.archivo, solicitante_id=self.actor)
            self.repo.marcar_limpiado(archivo_id=self.archivo, solicitante_id=self.actor)
            self.repo.marcar_limpiado(archivo_id=self.archivo, solicitante_id=self.actor)
            self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.CANCELED)
        self.assertEqual(IntentoPublicacion.objects.get().estado, EstadoPublicacion.CLEANED)

    def test_expirar_solo_despues_del_vencimiento(self):
        sesion = self.crear()
        with self.repo.unidad_de_trabajo(organizacion_id=self.org), self.assertRaises(EstadoIncompatible):
            self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.EXPIRED)
        SesionCarga.objects.filter(pk=sesion.pk).update(creado_en=timezone.now()-timedelta(days=2),
                                                     expira_en=timezone.now()-timedelta(days=1))
        with self.repo.unidad_de_trabajo(organizacion_id=self.org):
            self.repo.finalizar_sin_publicar(archivo_id=self.archivo, solicitante_id=self.actor, estado=EstadoSesion.EXPIRED)
        self.assertEqual(SesionCarga.objects.get().estado, EstadoSesion.EXPIRED)

    def test_fk_carpeta_set_null_y_ledger_restringe_borrado(self):
        sesion = self.crear()
        self.preparar()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM carpetas WHERE id=%s", [self.carpeta])
        sesion.refresh_from_db()
        self.assertIsNone(sesion.carpeta_id)  # Revalidación de destino obligatoria en fase 05
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM sesiones_carga WHERE id=%s", [sesion.pk])

    def test_rollback_no_deja_sesion_y_libera_lock(self):
        with self.assertRaises(RuntimeError):
            with self.repo.unidad_de_trabajo(organizacion_id=self.org):
                self.repo.crear_sesion(archivo_id=self.archivo, destino=self.destino, nombre="a.pdf", tipo_mime="application/pdf",
                    tamano_bytes=0, clave_temporal="tmp/rollback", expira_en=timezone.now()+timedelta(minutes=5))
                raise RuntimeError("Fallo sintético")
        self.assertFalse(SesionCarga.objects.exists())
        self.crear()

    def test_recuperacion_en_otro_proceso(self):
        sesion = self.crear()
        intento = self.preparar()
        codigo = """import django, json, sys; django.setup()
from almacenamiento.models import SesionCarga, IntentoPublicacion
s=SesionCarga.objects.get(archivo_id=sys.argv[1],solicitante_id=sys.argv[2])
i=IntentoPublicacion.objects.get(sesion=s)
print(json.dumps([str(s.id),s.estado,str(i.id),i.estado]))"""
        resultado = subprocess.run([sys.executable, "-c", codigo, str(self.archivo), str(self.actor)],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "almacenamiento.tests_persistencia.settings"},
            capture_output=True, text=True, check=True, timeout=15)
        self.assertEqual(json.loads(resultado.stdout), [str(sesion.pk), "PENDING", str(intento.pk), "PREPARED"])

    def test_lock_compartido_serializa_dos_conexiones_y_libera_al_commit(self):
        self.crear()
        primero_dentro, segundo_iniciado, liberar_primero, segundo_dentro = Event(), Event(), Event(), Event()
        def primero():
            repo = RepositorioCargas()
            try:
                with repo.unidad_de_trabajo(organizacion_id=self.org):
                    primero_dentro.set()
                    if not liberar_primero.wait(5):
                        raise RuntimeError("Tiempo agotado en test de bloqueo")
                    return repo.preparar_publicacion(archivo_id=self.archivo, solicitante_id=self.actor,
                        clave_final="final/concurrente", etag_origen="origen").pk
            finally:
                connections.close_all()
        def segundo():
            repo = RepositorioCargas()
            try:
                segundo_iniciado.set()
                with repo.unidad_de_trabajo(organizacion_id=self.org):
                    segundo_dentro.set()
                    return repo.preparar_publicacion(archivo_id=self.archivo, solicitante_id=self.actor,
                        clave_final="final/concurrente", etag_origen="origen").pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            uno = pool.submit(primero)
            self.assertTrue(primero_dentro.wait(5))
            dos = pool.submit(segundo)
            try:
                self.assertTrue(segundo_iniciado.wait(5))
                self.assertFalse(segundo_dentro.wait(0.2))
            finally:
                liberar_primero.set()
            self.assertEqual(uno.result(timeout=5), dos.result(timeout=5))
        self.assertTrue(segundo_dentro.is_set())
        self.assertEqual(IntentoPublicacion.objects.count(), 1)

    def test_clave_lock_estable_y_tipado(self):
        self.assertEqual(clave_bloqueo_cuota(self.org), clave_bloqueo_cuota(self.org))
        self.assertNotEqual(clave_bloqueo_cuota(self.org), clave_bloqueo_cuota(self.otra_org))
        self.assertTrue(-(1 << 63) <= clave_bloqueo_cuota(self.org) < (1 << 63))
        with self.assertRaises(TypeError):
            clave_bloqueo_cuota(str(self.org))

    def test_inspector_detecta_trigger_deshabilitado_sin_repararlo(self):
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE sesiones_carga DISABLE TRIGGER trg_actualizar_sesiones_carga")
        try:
            self.assertFalse(inspeccionar_esquema().compatible)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE sesiones_carga ENABLE TRIGGER trg_actualizar_sesiones_carga")

    def test_inspector_detecta_check_y_fk_incompatibles(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE sesiones_carga DROP CONSTRAINT sesiones_carga_tamano_bytes_check")
                cursor.execute("ALTER TABLE sesiones_carga DROP CONSTRAINT sesiones_carga_carpeta_id_fkey")
                cursor.execute("ALTER TABLE sesiones_carga ADD FOREIGN KEY (carpeta_id) REFERENCES carpetas(id) ON DELETE CASCADE")
            informe = inspeccionar_esquema()
            self.assertFalse(informe.compatible)
            self.assertTrue(any("tamano_bytes" in problema for problema in informe.problemas))
            self.assertTrue(any("carpeta_id" in problema for problema in informe.problemas))
            transaction.set_rollback(True)  # Devolver la referencia literal para el caso siguiente

    def test_inspector_detecta_indice_ausente(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DROP INDEX idx_sesiones_cuota_pendiente")
            self.assertFalse(inspeccionar_esquema().compatible)
            transaction.set_rollback(True)
