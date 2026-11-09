"""Guardias preparatorias; no habilitan rutas ni privilegios de plataforma.

La identidad debe proceder de CloudVaultJWTAuthentication en la vista. Las
consultas siguientes vuelven a comprobar cuenta y membresía sin crear espacios
legados. No sustituyen la revocación durable de sesiones, ausente en el esquema.
"""

from enum import Enum
from uuid import UUID

from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import BasePermission

from common.ambito import Ambito
from subscriptions.models import MiembroOrganizacion

from .models import Usuario


class AccionOrganizacion(Enum):
    LISTAR_MIEMBROS = "listar_miembros"
    INVITAR = "invitar"
    LISTAR_INVITACIONES = "listar_invitaciones"
    REVOCAR_INVITACION = "revocar_invitacion"
    CAMBIAR_ROL = "cambiar_rol"
    RETIRAR_MIEMBRO = "retirar_miembro"
    LEER_AUDITORIA = "leer_auditoria"


_ROLES_POR_ACCION = {
    accion: frozenset({0}) for accion in AccionOrganizacion
}
_ROLES_POR_ACCION[AccionOrganizacion.LISTAR_MIEMBROS] = frozenset({0, 1, 2, 3})


def _cuenta_vigente(usuario):
    if usuario is None or not usuario.is_authenticated:
        raise NotAuthenticated()
    try:
        cuenta = Usuario.objects.only("id", "is_active", "is_2fa_enabled").get(
            pk=usuario.pk
        )
    except Usuario.DoesNotExist as exc:
        raise AuthenticationFailed() from exc
    if not cuenta.is_active or cuenta.is_2fa_enabled:
        raise AuthenticationFailed()
    return cuenta


def autorizar_organizacion(usuario, organizacion_id, accion):
    """Autoriza solo una acción enumerada en una organización explícita.

    No infiere ámbito personal ni permite intervención global. Los errores del
    repositorio se propagan: nunca se reutiliza una autorización anterior. Esto
    solo comprueba acceso; las mutaciones futuras deben revalidarlo dentro de su
    transacción y comprobar dueño, plan, auditoría y efectos de compartir.
    """
    cuenta = _cuenta_vigente(usuario)
    if not isinstance(accion, AccionOrganizacion):
        raise PermissionDenied()
    try:
        pedido = UUID(str(organizacion_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({
            "organizacion_id": ["Se requiere un UUID de organización explícito."]
        }) from exc

    nivel = (
        MiembroOrganizacion.objects.filter(
            usuario_id=cuenta.pk, organizacion_id=pedido
        )
        .values_list("nivel_rol", flat=True)
        .first()
    )
    if nivel is None:
        raise NotFound()
    if type(nivel) is not int or nivel not in _ROLES_POR_ACCION[accion]:
        raise PermissionDenied()
    return Ambito(organizacion_id=pedido, nivel_rol=nivel)


class ExigeSuperusuario(BasePermission):
    """Deniega plataforma mientras no exista una fuente persistente legítima.

    El esquema vigente no contiene ese privilegio. No consultar atributos
    is_superuser añadidos al objeto, claims, roles locales, correos o settings
    como sustituto. Cualquier implementación futura exige nueva revisión.
    """

    def has_permission(self, request, view):
        _cuenta_vigente(request.user)
        return False
