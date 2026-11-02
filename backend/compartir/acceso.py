"""Quién puede ver, descargar o subir en un recurso compartido.

Un permiso sobre una carpeta se hereda en todo su subárbol (como en Drive). Los permisos
obtenidos por enlace (``enlace_id``) siguen las condiciones vigentes del enlace.
"""

from dataclasses import dataclass

from django.db import connections
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .models import ESCRITURA, LECTURA, EnlacePublico

# Ancestros de una carpeta (ella incluida); se corta en la primera carpeta en papelera.
CADENA = """WITH RECURSIVE cadena(id, padre) AS (
    SELECT id, carpeta_padre_id FROM carpetas WHERE id = %s AND NOT en_papelera
    UNION
    SELECT c.id, c.carpeta_padre_id FROM carpetas c JOIN cadena ON c.id = cadena.padre
    WHERE NOT c.en_papelera)
"""


@dataclass(frozen=True)
class Acceso:
    rol: str
    permite_descarga: bool
    organizacion_id: object


def _recurso(cursor, archivo_id, carpeta_id):
    """(organizacion_id, carpeta de partida) del recurso fuera de la papelera, o None."""
    if archivo_id is not None:
        cursor.execute("SELECT organizacion_id, carpeta_id FROM archivos WHERE id = %s AND NOT en_papelera",
                       [archivo_id])
    else:
        cursor.execute("SELECT organizacion_id, id FROM carpetas WHERE id = %s AND NOT en_papelera",
                       [carpeta_id])
    return cursor.fetchone()


def acceso_usuario(usuario_id, *, archivo_id=None, carpeta_id=None, using="default"):
    """Acceso por ACL (no por membresía) de ``usuario_id`` al recurso, o None."""
    with connections[using].cursor() as cursor:
        recurso = _recurso(cursor, archivo_id, carpeta_id)
        if recurso is None:
            return None
        cursor.execute(CADENA + """
            SELECT COALESCE(e.rol, p.tipo_permiso), COALESCE(e.permite_descarga, p.permite_descarga)
            FROM permisos_recurso p LEFT JOIN enlaces_publicos e ON e.id = p.enlace_id
            WHERE p.usuario_id = %s AND (p.carpeta_id IN (SELECT id FROM cadena) OR p.archivo_id = %s)
              AND (e.id IS NULL OR e.fecha_expiracion IS NULL OR e.fecha_expiracion > now())""",
                       [recurso[1], usuario_id, archivo_id])
        filas = cursor.fetchall()
    if not filas:
        return None
    escritura = any(rol == ESCRITURA for rol, _ in filas)
    descarga = escritura or any(d for _, d in filas)
    return Acceso(ESCRITURA if escritura else LECTURA, descarga, recurso[0])


def enlace_vigente(token):
    enlace = (EnlacePublico.objects.select_related("archivo", "carpeta")
              .filter(token=token).first() if isinstance(token, str) else None)
    if (enlace is None or (enlace.fecha_expiracion and enlace.fecha_expiracion <= timezone.now())
            or enlace.recurso.en_papelera):
        raise NotFound()
    return enlace


def dentro_del_enlace(enlace, *, archivo=None, carpeta_id=None, using="default"):
    """¿El archivo o la carpeta pertenecen a lo que comparte el enlace (y no están en papelera)?"""
    if archivo is not None and archivo.en_papelera:
        return False
    if enlace.archivo_id is not None:
        return archivo is not None and archivo.pk == enlace.archivo_id
    partida = archivo.carpeta_id if archivo is not None else carpeta_id
    if partida is None:
        return False
    with connections[using].cursor() as cursor:
        cursor.execute(CADENA + "SELECT 1 FROM cadena WHERE id = %s", [partida, enlace.carpeta_id])
        return cursor.fetchone() is not None


def es_miembro(usuario_id, organizacion_id, using="default"):
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT 1 FROM miembros_organizacion WHERE usuario_id = %s AND organizacion_id = %s",
                       [usuario_id, organizacion_id])
        return cursor.fetchone() is not None


def unirse(enlace, usuario_id, using="default"):
    """Registra al usuario con sesión que abre el enlace (aparece en "Compartido conmigo")."""
    if es_miembro(usuario_id, enlace.recurso.organizacion_id, using):
        return False
    # ponytail: si ya tiene un permiso directo (p. ej. LECTURA) no se toca; el enlace no lo eleva.
    # Habría que fusionar roles si los usuarios lo piden.
    with connections[using].cursor() as cursor:
        cursor.execute(
            """INSERT INTO permisos_recurso
                   (archivo_id, carpeta_id, usuario_id, tipo_permiso, permite_descarga, enlace_id)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            [enlace.archivo_id, enlace.carpeta_id, usuario_id, enlace.rol, enlace.permite_descarga, enlace.pk])
    return True
