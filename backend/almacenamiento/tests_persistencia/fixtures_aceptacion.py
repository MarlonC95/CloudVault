"""Política/SQL exclusivos del clúster desechable; no son servicios de German.

Dos organizaciones, cuatro roles, dos carpetas y suscripciones reales en SQL.
Solo se importan desde tests; ninguna factory de producción apunta aquí.
"""

from datetime import timedelta
from uuid import uuid4

from django.db import connections
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga
from almacenamiento.integracion import (
    ArchivoVerificado, CuotaVigente, DestinoAutorizado, InspeccionObjetoTecnico,
)
from almacenamiento.persistencia import RepositorioCargas


class ProveedorEnsayo:
    using = "default"

    def __init__(self, *, trigger=False):
        self.trigger = trigger
        self.organizaciones = [uuid4(), uuid4()]
        self.carpetas = [uuid4(), uuid4()]
        self.actores = [uuid4() for _ in range(5)]
        self.bloquear_cuota = RepositorioCargas().unidad_de_trabajo

    def sembrar(self):
        with connections[self.using].cursor() as c:
            c.execute("TRUNCATE organizaciones, usuarios, planes CASCADE")
            for actor in self.actores:
                c.execute("""INSERT INTO usuarios
                    (id,nombre_completo,correo_electronico,contrasena_hash,palabra_secreta_hash)
                    VALUES (%s,'Ensayo',%s,'hash-sintetico','hash-sintetico')""",
                    [actor, f"{actor}@example.test"])
            for i, org in enumerate(self.organizaciones):
                c.execute("INSERT INTO organizaciones (id,nombre,slug) VALUES (%s,'Ensayo',%s)", [org, str(org)])
                c.execute("INSERT INTO planes (nombre,limite_almacenamiento_bytes) VALUES (%s,20) RETURNING id", [str(i)])
                plan = c.fetchone()[0]
                c.execute("""INSERT INTO suscripciones (organizacion_id,plan_id,periodo_inicio,periodo_fin)
                    VALUES (%s,%s,%s,%s)""", [org, plan, timezone.now()-timedelta(days=1), timezone.now()+timedelta(days=1)])
                propietario = self.actores[0 if i == 0 else 4]
                c.execute("INSERT INTO carpetas (id,organizacion_id,propietario_id,nombre) VALUES (%s,%s,%s,'Ensayo')",
                          [self.carpetas[i], org, propietario])
            for rol, actor in enumerate(self.actores[:4]):
                c.execute("INSERT INTO miembros_organizacion (organizacion_id,usuario_id,nivel_rol) VALUES (%s,%s,%s)",
                          [self.organizaciones[0], actor, rol])
            c.execute("INSERT INTO miembros_organizacion (organizacion_id,usuario_id,nivel_rol) VALUES (%s,%s,0)",
                      [self.organizaciones[1], self.actores[4]])

    def resolver_destino(self, *, solicitante_id, carpeta_id):
        with connections[self.using].cursor() as c:
            if carpeta_id is None:
                c.execute("SELECT organizacion_id,nivel_rol FROM miembros_organizacion WHERE usuario_id=%s", [solicitante_id])
            else:
                c.execute("""SELECT m.organizacion_id,m.nivel_rol FROM miembros_organizacion m
                    JOIN carpetas f ON f.organizacion_id=m.organizacion_id
                    WHERE m.usuario_id=%s AND f.id=%s AND NOT f.en_papelera""", [solicitante_id, carpeta_id])
            filas = c.fetchall()
        if len(filas) > 1:
            raise ErrorCarga(CodigoError.VALIDATION_ERROR)
        if not filas or filas[0][1] not in (0, 2, 3):
            raise PermissionDenied()
        return DestinoAutorizado(solicitante_id, filas[0][0], carpeta_id)

    def leer_cuota(self, *, organizacion_id):
        with connections[self.using].cursor() as c:
            c.execute("""SELECT p.limite_almacenamiento_bytes,o.almacenamiento_usado_bytes,s.periodo_fin
                FROM organizaciones o JOIN suscripciones s ON s.organizacion_id=o.id
                JOIN planes p ON p.id=s.plan_id WHERE o.id=%s AND o.esta_activo
                AND p.esta_activo AND s.estado='ACTIVE' AND s.periodo_inicio<=CURRENT_TIMESTAMP
                AND s.periodo_fin>CURRENT_TIMESTAMP""", [organizacion_id])
            filas = c.fetchall()
        if len(filas) != 1:
            raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
        return CuotaVigente(organizacion_id, *filas[0])

    def registrar_archivo(self, *, archivo):
        assert connections[self.using].in_atomic_block
        with connections[self.using].cursor() as c:
            c.execute("""INSERT INTO archivos (id,organizacion_id,carpeta_id,propietario_id,
                nombre_original,clave_s3,tamano_bytes,tipo_mime,checksum_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", [archivo.archivo_id,
                archivo.organizacion_id, archivo.carpeta_id, archivo.solicitante_id,
                archivo.nombre, archivo.clave_final, archivo.tamano_bytes, archivo.tipo_mime, archivo.checksum_sha256])
            if not self.trigger:
                c.execute("UPDATE organizaciones SET almacenamiento_usado_bytes=almacenamiento_usado_bytes+%s WHERE id=%s",
                          [archivo.tamano_bytes, archivo.organizacion_id])

    def autorizar_descarga(self, *, solicitante_id, archivo_id):
        with connections[self.using].cursor() as c:
            c.execute("""SELECT a.id,a.organizacion_id,a.carpeta_id,a.nombre_original,a.clave_s3,
                a.tamano_bytes,a.tipo_mime,a.checksum_sha256 FROM archivos a
                JOIN miembros_organizacion m ON m.organizacion_id=a.organizacion_id
                WHERE a.id=%s AND m.usuario_id=%s AND NOT a.en_papelera""", [archivo_id, solicitante_id])
            fila = c.fetchone()
        if fila is None:
            raise ErrorCarga(CodigoError.NO_ENCONTRADO)
        return ArchivoVerificado(fila[0], solicitante_id, *fila[1:])

    def inspeccionar_objeto_tecnico(self, *, sesion_id, organizacion_id, clave):
        with connections[self.using].cursor() as c:
            c.execute("SELECT EXISTS(SELECT 1 FROM archivos WHERE clave_s3=%s)", [clave])
            referenciado = c.fetchone()[0]
        # El ACK propio de COPY determina conclusión; no inventar prueba externa.
        return InspeccionObjetoTecnico(sesion_id, organizacion_id, clave, referenciado)
