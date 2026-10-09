"""Resolución de la organización (espacio de trabajo) sobre la que opera una petición.

Reglas acordadas con el DBA (el esquema SQL manda; ``miembros_organizacion.nivel_rol``:
0 propietario/admin, 1 lector, 2 operativo, 3 avanzado):

* ``organizacion_id`` informado: el usuario debe ser miembro, si no => 404 NO_ENCONTRADO
  (no se revela si la organización existe).
* omitido: se usa la única membresía; varias => 400 VALIDATION_ERROR
  (``fields.organizacion_id``); ninguna => 403 SIN_PERMISO.
* operaciones de escritura exigen ``nivel_rol`` en (0, 2, 3); el nivel 1 solo lee.
"""

from dataclasses import dataclass
from uuid import UUID

from django.db import connections
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

NIVELES_ESCRITURA = frozenset({0, 2, 3})
NIVEL_ADMIN = 0


@dataclass(frozen=True)
class Ambito:
    organizacion_id: UUID
    nivel_rol: int

    @property
    def puede_escribir(self):
        return self.nivel_rol in NIVELES_ESCRITURA

    @property
    def es_admin(self):
        return self.nivel_rol == NIVEL_ADMIN


def _a_uuid(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, UUID):
        return valor
    try:
        return UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError({"organizacion_id": ["El identificador de organización no es válido."]})


def resolver_organizacion(usuario, organizacion_id=None, escritura=False, using="default"):
    """Devuelve el ``Ambito`` del usuario o lanza una excepción DRF del contrato."""
    pedido = _a_uuid(organizacion_id)
    with connections[using].cursor() as cursor:
        cursor.execute(
            """SELECT m.organizacion_id, m.nivel_rol
               FROM miembros_organizacion m
               JOIN organizaciones o ON o.id = m.organizacion_id
               WHERE m.usuario_id = %s
               ORDER BY m.fecha_union, m.organizacion_id""",
            [usuario.pk],
        )
        membresias = cursor.fetchall()
    if pedido is not None:
        elegida = next((m for m in membresias if m[0] == pedido), None)
        if elegida is None:
            raise NotFound()
    elif not membresias:
        raise PermissionDenied()
    elif len(membresias) > 1:
        raise ValidationError(
            {"organizacion_id": ["Indica la organización: perteneces a más de una."]}
        )
    else:
        elegida = membresias[0]
    ambito = Ambito(organizacion_id=elegida[0], nivel_rol=int(elegida[1]))
    if escritura and not ambito.puede_escribir:
        raise PermissionDenied()
    return ambito
