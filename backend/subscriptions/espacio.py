"""Creación idempotente del espacio personal de un usuario.

El flujo de registro lo consume dentro de su transacción; también puede
invocarse para usuarios legados sin membresía.
"""

import re
import secrets
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from auth_workspaces.models import Usuario

from .models import MiembroOrganizacion, Organizacion, Plan, Suscripcion


def _slug_usuario(correo):
    local = correo.split("@")[0]
    limpio = re.sub(r"[^a-z0-9]+", "-", local.lower()).strip("-") or "usuario"
    return limpio[:50]


def _generar_slug(correo):
    base = _slug_usuario(correo)
    return f"workspace-{base}-{secrets.token_hex(4)}"


def crear_espacio(usuario, *, nombre, tipo, organizacion_id=None, plan_id=None):
    """Inicializa un espacio y su cuota dentro de la transacción del llamador."""
    slug = _generar_slug(usuario.correo_electronico)

    for _ in range(5):
        try:
            with transaction.atomic():
                organizacion = Organizacion.objects.create(
                    nombre=nombre,
                    slug=slug,
                    tipo=tipo,
                    **({"id": organizacion_id} if organizacion_id is not None else {}),
                )
        except IntegrityError:
            slug = _generar_slug(usuario.correo_electronico)
            continue
        break
    else:
        raise IntegrityError("No fue posible generar un slug único para la organización.")

    MiembroOrganizacion.objects.create(
        organizacion_id=organizacion.id,
        usuario_id=usuario.id,
        nivel_rol=0,
    )

    ahora = timezone.now()
    if plan_id is None:
        plan_id = Plan.objects.filter(esta_activo=True, id=1).values_list("id", flat=True).first() or 1
    Suscripcion.objects.create(
        organizacion_id=organizacion.id,
        plan_id=plan_id,
        estado=Suscripcion.ESTADO_ACTIVE,
        intervalo=Suscripcion.INTERVALO_MENSUAL,
        periodo_inicio=ahora,
        periodo_fin=ahora.replace(year=ahora.year + 10, day=28 if (ahora.month, ahora.day) == (2, 29) else ahora.day),
        auto_renovar=True,
    )

    return organizacion.id


def asegurar_espacio_personal(usuario_id) -> UUID:
    """Devuelve el id de la organización personal del usuario, creándola si falta.

    Es idempotente y utiliza ``select_for_update`` sobre el usuario para evitar
    condiciones de carrera cuando varios hilos llaman simultáneamente.
    """
    usuario_id = UUID(str(usuario_id))

    with transaction.atomic():
        usuario = Usuario.objects.select_for_update().get(pk=usuario_id)

        membresia = (
            MiembroOrganizacion.objects.filter(
                usuario_id=usuario_id, nivel_rol=0,
                organizacion_id__in=Organizacion.objects.filter(tipo=Organizacion.PERSONAL).values("pk"),
            )
            .order_by("fecha_union")
            .first()
        )
        if membresia is not None:
            return membresia.organizacion_id

        return crear_espacio(
            usuario, nombre=f"Espacio de {usuario.nombre_completo}"[:150], tipo=Organizacion.PERSONAL,
        )
