"""Diagnóstico del diario con PostgreSQL privado y DDL revertido por caso."""

from django.db import connection, transaction
from django.test import SimpleTestCase
from psycopg import sql

from almacenamiento.esquema import inspeccionar_esquema
from almacenamiento.models import TrabajoMantenimiento


TABLA = "public.trabajos_mantenimiento"


class EsquemaMantenimientoTests(SimpleTestCase):
    databases = {"default"}

    def diagnosticar_cambio(self, sentencia, fragmento):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sentencia)
            informe = inspeccionar_esquema()
            self.assertFalse(informe.compatible)
            self.assertTrue(any(fragmento in problema for problema in informe.problemas),
                            informe.problemas)
            transaction.set_rollback(True)
        self.assertTrue(inspeccionar_esquema().compatible)

    def test_referencia_completa_inspeccionada_en_transaccion_solo_lectura(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
            self.assertTrue(inspeccionar_esquema().compatible)

    def test_tabla_ausente_no_es_recreada(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {TABLA} RENAME TO diario_apartado")
            self.assertIn(f"Falta {TABLA}", inspeccionar_esquema().problemas)
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", [TABLA])
                self.assertIsNone(cursor.fetchone()[0])
            transaction.set_rollback(True)
        self.assertTrue(inspeccionar_esquema().compatible)

    def test_tipos_booleano_entero_bigint_y_longitudes(self):
        for columna, tipo, expresion in (
            ("cancelar", "integer", "CASE WHEN cancelar THEN 1 ELSE 0 END"),
            ("copia_concluida", "integer", "CASE WHEN copia_concluida THEN 1 ELSE 0 END"),
            ("intentos", "integer", "intentos::integer"),
            ("fallos_consecutivos", "bigint", "fallos_consecutivos::bigint"),
            ("estado", "varchar(20)", "estado"),
            ("causa", "varchar(40)", "causa"),
        ):
            with self.subTest(columna=columna):
                self.diagnosticar_cambio(
                    f"ALTER TABLE {TABLA} ALTER COLUMN {columna} DROP DEFAULT, "
                    f"ALTER COLUMN {columna} TYPE {tipo} USING {expresion}",
                    f"{TABLA}.{columna}")

    def test_columna_ausente_y_nulabilidad_incompatibles(self):
        self.diagnosticar_cambio(f"ALTER TABLE {TABLA} RENAME COLUMN cancelar TO cancelar_apartado",
                                f"{TABLA}.cancelar")
        self.diagnosticar_cambio(f"ALTER TABLE {TABLA} ALTER COLUMN proximo_intento DROP NOT NULL",
                                f"{TABLA}.proximo_intento")

    def test_unicidad_no_sustituye_clave_primaria(self):
        self.diagnosticar_cambio(
            f"ALTER TABLE {TABLA} DROP CONSTRAINT trabajos_mantenimiento_pkey, "
            "ADD UNIQUE (sesion_id)", f"Falta PK: {TABLA}.sesion_id")

    def test_fk_debe_ser_validada_restrict_y_apuntar_a_sesion_publica(self):
        for referencia, borrado, validacion in (
            ("public.sesiones_carga(id)", "CASCADE", ""),
            ("public.sesiones_carga(id)", "RESTRICT", "NOT VALID"),
            (f"{TABLA}(sesion_id)", "RESTRICT", ""),
        ):
            with self.subTest(referencia=referencia, borrado=borrado, validacion=validacion):
                self.diagnosticar_cambio(
                    f"ALTER TABLE {TABLA} DROP CONSTRAINT trabajos_mantenimiento_sesion_id_fkey, "
                    f"ADD FOREIGN KEY (sesion_id) REFERENCES {referencia} ON DELETE {borrado} {validacion}",
                    f"Falta FK: {TABLA}.sesion_id")

    def test_cada_check_debe_existir_y_estar_validado(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                           "WHERE conrelid=to_regclass(%s) AND contype='c'", [TABLA])
            checks = cursor.fetchall()
        self.assertEqual(len(checks), 5)
        for nombre, definicion in checks:
            for invalidar in (False, True):
                with self.subTest(check=nombre, invalidar=invalidar):
                    sentencia = sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                        sql.Identifier("public", "trabajos_mantenimiento"),
                        sql.Identifier(nombre))
                    if invalidar:
                        sentencia += sql.SQL(", ADD CONSTRAINT {} {} NOT VALID").format(
                            sql.Identifier(nombre), sql.SQL(definicion))
                    self.diagnosticar_cambio(sentencia, f"CHECK ausente o diferente en {TABLA}")

    def test_indice_ausente_orden_incorrecto_o_parcial(self):
        for reemplazo in (None, "(sesion_id, proximo_intento)",
                          "(proximo_intento, sesion_id) WHERE estado='PENDING'"):
            with self.subTest(reemplazo=reemplazo), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("ALTER INDEX public.idx_mantenimiento_proximo "
                                   "RENAME TO indice_apartado")
                    if reemplazo:
                        cursor.execute(f"CREATE INDEX idx_mantenimiento_proximo ON {TABLA} {reemplazo}")
                self.assertIn(f"Falta índice vigente: {TABLA}.idx_mantenimiento_proximo",
                              inspeccionar_esquema().problemas)
                transaction.set_rollback(True)
            self.assertTrue(inspeccionar_esquema().compatible)

    def test_modelo_resuelve_public_sin_depender_del_search_path(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL search_path TO pg_catalog")
            # La consulta funciona aun cuando public está fuera del search_path.
            self.assertIsInstance(TrabajoMantenimiento.objects.exists(), bool)

    def test_trigger_deshabilitado_es_detectado_sin_habilitarlo(self):
        self.diagnosticar_cambio(
            f"ALTER TABLE {TABLA} DISABLE TRIGGER trg_actualizar_trabajos_mantenimiento",
            f"Falta trigger de timestamps habilitado: {TABLA}")

    def test_rol_auditoria_puede_leer_pero_no_escribir_el_diario(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE lector_cloudvault")
                self.assertIsInstance(TrabajoMantenimiento.objects.exists(), bool)
            problemas = inspeccionar_esquema().problemas
            self.assertIn(f"Falta permiso INSERT: {TABLA}", problemas)
            self.assertIn(f"Falta permiso UPDATE: {TABLA}", problemas)
            self.assertNotIn(f"Falta permiso SELECT: {TABLA}", problemas)
        self.assertTrue(inspeccionar_esquema().compatible)
