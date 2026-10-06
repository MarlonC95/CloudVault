"""Inspección de solo lectura: nunca instala ni repara el SQL compartido."""

from dataclasses import dataclass
import re

from django.db import connections, models

from .models import IntentoPublicacion, SesionCarga


def _normalizar_check(definicion):
    # Representación conservadora del SQL vigente. Una definición diferente se
    # reporta para revisión, aunque pudiera resultar equivalente.
    sin_casts = re.sub(r"::(?:character varying|text)(?:\[\])?", "", definicion)
    return re.sub(r"[\s()]", "", sin_casts)


@dataclass(frozen=True)
class InformeEsquema:
    problemas: tuple[str, ...]
    advertencias: tuple[str, ...]
    triggers_archivos: tuple[str, ...]

    @property
    def compatible(self):
        return not self.problemas


def inspeccionar_esquema(*, using="default") -> InformeEsquema:
    connection = connections[using]
    if connection.vendor != "postgresql":
        return InformeEsquema(("Se requiere PostgreSQL",), (), ())
    problemas, advertencias = [], []
    with connection.cursor() as cursor:
        for modelo in (SesionCarga, IntentoPublicacion):
            tabla = modelo._meta.db_table
            cursor.execute("SELECT to_regclass(%s)", [tabla])
            if cursor.fetchone()[0] is None:
                problemas.append(f"Falta {tabla}")
                continue
            cursor.execute("""
                SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
                FROM pg_attribute a WHERE a.attrelid=to_regclass(%s)
                AND a.attnum>0 AND NOT a.attisdropped
            """, [tabla])
            columnas = {nombre: (tipo, obligatorio) for nombre, tipo, obligatorio in cursor.fetchall()}
            for campo in modelo._meta.local_fields:
                if isinstance(campo, models.CharField):
                    tipo = f"character varying({campo.max_length})"
                elif isinstance(campo, models.DateTimeField):
                    tipo = "timestamp with time zone"
                elif isinstance(campo, models.JSONField):
                    tipo = "jsonb"
                elif isinstance(campo, models.BigIntegerField):
                    tipo = "bigint"
                else:
                    tipo = "uuid"
                if columnas.get(campo.column) != (tipo, not campo.null):
                    problemas.append(f"Mapping incompatible: {tabla}.{campo.column}")
            restricciones = connection.introspection.get_constraints(cursor, tabla)
            cursor.execute("""SELECT conname, pg_get_constraintdef(oid), confdeltype, convalidated
                              FROM pg_constraint WHERE conrelid=to_regclass(%s)""", [tabla])
            definiciones = {nombre: (definicion, borrado, validada)
                            for nombre, definicion, borrado, validada in cursor.fetchall()}
            for campo in modelo._meta.local_fields:
                if (campo.unique or campo.primary_key) and not any(
                    r["columns"] == [campo.column] and (r["unique"] or r["primary_key"])
                    for r in restricciones.values()
                ):
                    problemas.append(f"Falta unicidad: {tabla}.{campo.column}")
            fks = {"solicitante_id": (("usuarios", "id"), "r"), "organizacion_id": (("organizaciones", "id"), "c"),
                   "carpeta_id": (("carpetas", "id"), "n")} if modelo is SesionCarga else {"sesion_id": (("sesiones_carga", "id"), "r")}
            for columna, (referencia, borrado) in fks.items():
                if not any(r["columns"] == [columna] and r["foreign_key"] == referencia
                           and definiciones.get(nombre, (None, None, False))[1:] == (borrado, True)
                           for nombre, r in restricciones.items()):
                    problemas.append(f"Falta FK: {tabla}.{columna}")
            checks = ["CHECK (estado = ANY (ARRAY['PREPARED', 'PUBLISHED', 'ABANDONED', 'CLEANED']))"]
            if modelo is SesionCarga:
                checks = ["CHECK (tamano_bytes >= 0)",
                          "CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$')",
                          "CHECK (estado = ANY (ARRAY['PENDING', 'CONFIRMED', 'CANCELED', 'EXPIRED']))",
                          "CHECK (expira_en > creado_en)"]
            checks_reales = {_normalizar_check(d) for d, _, validada in definiciones.values() if validada and d.startswith("CHECK ")}
            for check in checks:
                if _normalizar_check(check) not in checks_reales:
                    problemas.append(f"CHECK ausente o diferente en {tabla}: {check}")
            if modelo is SesionCarga:
                cursor.execute("""SELECT pg_get_expr(i.indpred,i.indrelid), i.indisvalid,
                    pg_get_indexdef(i.indexrelid,1,true), pg_get_indexdef(i.indexrelid,2,true)
                    FROM pg_index i WHERE i.indexrelid=to_regclass('idx_sesiones_cuota_pendiente')
                    AND i.indrelid=to_regclass(%s)""", [tabla])
                indice = cursor.fetchone()
                if (indice is None or not indice[1] or indice[2:] != ("organizacion_id", "expira_en")
                        or _normalizar_check(indice[0] or "") != "estado='PENDING'"):
                    problemas.append("Falta índice parcial vigente de reservas")
            cursor.execute("""SELECT EXISTS (
                SELECT 1 FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
                WHERE t.tgrelid=to_regclass(%s) AND t.tgname=%s
                AND t.tgenabled IN ('O','A') AND NOT t.tgisinternal
                AND p.proname='trigger_actualizar_marca_tiempo' AND t.tgtype=19
            )""", [tabla, f"trg_actualizar_{tabla}"])
            if not cursor.fetchone()[0]:
                problemas.append(f"Falta trigger de timestamps habilitado: {tabla}")
        cursor.execute("""SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass('archivos')
                          AND NOT tgisinternal AND tgenabled IN ('O','A') ORDER BY tgname""")
        triggers = tuple(row[0] for row in cursor.fetchall())
        if not triggers:
            advertencias.append("Sin triggers de archivos: el esquema recibido no ajusta el uso de cuota")
        else:
            advertencias.append("Revisar función de cada trigger de archivos y acordar una sola autoridad de uso")
        cursor.execute("""SELECT EXISTS (SELECT 1 FROM pg_attribute
            WHERE attrelid=to_regclass('usuarios') AND attname='fecha_creacion' AND NOT attisdropped)""")
        if not cursor.fetchone()[0]:
            advertencias.append("Auth existente consulta usuarios.fecha_creacion; el esquema vigente usa creado_en")
    return InformeEsquema(tuple(problemas), tuple(advertencias), triggers)
