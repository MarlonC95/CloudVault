"""Quién puede ver, descargar o subir en un recurso compartido.

Un permiso sobre una carpeta se hereda en todo su subárbol (como en Drive). Los permisos
obtenidos por enlace (``enlace_id``) siguen las condiciones vigentes del enlace.
"""

from dataclasses import dataclass

from django.db import ProgrammingError, connections, transaction
from django.db.models import Case, F, Q, UUIDField, When
from django.db.models.expressions import RawSQL
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import ESCRITURA, LECTURA, EnlacePublico, PermisoRecurso
from subscriptions.models import MiembroOrganizacion, Organizacion

# La herencia se corta en la primera carpeta en papelera o fuera de la organización.
CADENA = """WITH RECURSIVE cadena(id, padre, organizacion_id) AS (
    SELECT id, carpeta_padre_id, organizacion_id FROM carpetas
    WHERE id = %s AND organizacion_id IS NOT DISTINCT FROM %s AND NOT en_papelera
    UNION
    SELECT c.id, c.carpeta_padre_id, c.organizacion_id
    FROM carpetas c JOIN cadena ON c.id = cadena.padre
    WHERE c.organizacion_id IS NOT DISTINCT FROM cadena.organizacion_id AND NOT c.en_papelera)
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
        try:
            with transaction.atomic(using=using):
                cursor.execute(CADENA + """
                    SELECT COALESCE(e.rol, p.tipo_permiso), COALESCE(e.permite_descarga, p.permite_descarga)
                    FROM permisos_recurso p LEFT JOIN enlaces_publicos e ON e.id = p.enlace_id
                    WHERE p.usuario_id = %s AND (p.carpeta_id IN (SELECT id FROM cadena) OR p.archivo_id = %s)
                      AND (e.id IS NULL OR e.fecha_expiracion IS NULL OR e.fecha_expiracion > now())""",
                               [recurso[1], recurso[0], usuario_id, archivo_id])
                filas = cursor.fetchall()
        except ProgrammingError as exc:
            if getattr(exc.__cause__, "sqlstate", None) != "42703":
                raise
            cursor.execute(CADENA + """
                SELECT p.tipo_permiso, TRUE
                FROM permisos_recurso p
                WHERE p.usuario_id = %s AND (p.carpeta_id IN (SELECT id FROM cadena) OR p.archivo_id = %s)""",
                           [recurso[1], recurso[0], usuario_id, archivo_id])
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
    organizacion_id = enlace.recurso.organizacion_id
    if archivo is not None and archivo.organizacion_id != organizacion_id:
        return False
    partida = archivo.carpeta_id if archivo is not None else carpeta_id
    if partida is None:
        return False
    with connections[using].cursor() as cursor:
        cursor.execute(CADENA + "SELECT 1 FROM cadena WHERE id = %s", [partida, organizacion_id, enlace.carpeta_id])
        return cursor.fetchone() is not None


def es_compartida(organizacion_id, using="default"):
    return Organizacion.objects.using(using).filter(pk=organizacion_id, tipo=Organizacion.COMPARTIDO).exists()


def carpetas_autorizadas(ambito, usuario_id):
    roles = [LECTURA, ESCRITURA]
    return RawSQL("""
        WITH RECURSIVE visibles(id) AS (
            SELECT c.id FROM carpetas c
            JOIN permisos_recurso p ON p.carpeta_id = c.id
            LEFT JOIN enlaces_publicos e ON e.id = p.enlace_id
            WHERE c.organizacion_id = %s AND NOT c.en_papelera AND p.usuario_id = %s
              AND COALESCE(e.rol, p.tipo_permiso) = ANY(%s)
              AND (p.enlace_id IS NULL OR e.id IS NOT NULL AND
                   (e.fecha_expiracion IS NULL OR e.fecha_expiracion > now()))
            UNION
            SELECT c.id FROM carpetas c JOIN visibles v ON c.carpeta_padre_id = v.id
            WHERE c.organizacion_id = %s AND NOT c.en_papelera
        )
        SELECT id FROM visibles
    """, (ambito.organizacion_id, usuario_id, roles, ambito.organizacion_id), output_field=UUIDField())


def archivos_visibles(consulta, ambito, usuario_id):
    if not ambito.requiere_permiso_recurso:
        return consulta
    directos = PermisoRecurso.objects.filter(
        usuario_id=usuario_id, archivo_id__isnull=False,
    ).filter(
        Q(enlace_id__isnull=True)
        | Q(enlace__fecha_expiracion__isnull=True)
        | Q(enlace__fecha_expiracion__gt=timezone.now()),
    ).values("archivo_id")
    carpetas = carpetas_autorizadas(ambito, usuario_id)
    visibles = consulta.filter(Q(propietario_id=usuario_id) | Q(pk__in=directos) | Q(carpeta_id__in=carpetas))
    return con_carpeta_visible(visibles, carpetas)


def con_carpeta_visible(consulta, carpetas):
    return consulta.annotate(carpeta_visible=Case(
        When(carpeta_id__in=carpetas, then=F("carpeta_id")), default=None, output_field=UUIDField(),
    ))


def exigir_edicion(ambito, usuario_id, *, archivo=None, carpeta_id=None):
    if not ambito.requiere_permiso_recurso:
        return
    if archivo is not None and archivo.propietario_id == usuario_id:
        return
    acceso = acceso_usuario(usuario_id, archivo_id=archivo.pk if archivo is not None else None, carpeta_id=carpeta_id)
    if acceso is None or acceso.organizacion_id != ambito.organizacion_id:
        raise NotFound()
    if acceso.rol != ESCRITURA:
        raise PermissionDenied()


def miembro_con_acceso_general(usuario_id, organizacion_id):
    nivel = MiembroOrganizacion.objects.filter(
        usuario_id=usuario_id, organizacion_id=organizacion_id,
    ).values_list("nivel_rol", flat=True).first()
    return nivel == 0 or (nivel in (1, 2, 3) and not es_compartida(organizacion_id))


def es_miembro(usuario_id, organizacion_id, using="default"):
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT 1 FROM miembros_organizacion WHERE usuario_id = %s AND organizacion_id = %s",
                       [usuario_id, organizacion_id])
        return cursor.fetchone() is not None


def unirse(enlace, usuario_id, using="default"):
    """Registra al usuario con sesión que abre el enlace (aparece en "Compartido conmigo")."""
    organizacion_id = enlace.recurso.organizacion_id
    if es_miembro(usuario_id, organizacion_id, using) and not es_compartida(organizacion_id, using):
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
