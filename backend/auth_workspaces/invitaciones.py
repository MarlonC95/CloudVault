"""Invitaciones en la aplicación para cuentas existentes."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from subscriptions.cuotas import SinSuscripcionVigente, leer_cuota_organizacion
from subscriptions.espacio import asegurar_espacio_personal, crear_espacio
from subscriptions.models import MiembroOrganizacion, Organizacion, Plan

from .gestion_miembros import ROLES, RepositorioMiembros
from .models import InvitacionOrganizacion as Invitacion
from .models import LogAuditoria, Usuario
from .permisos_administracion import AccionOrganizacion, autorizar_organizacion

VIGENCIA = timedelta(hours=48)


class ConflictoInvitacion(APIException):
    status_code = 409


class InvitacionesNoDisponibles(APIException):
    status_code = 503
    default_code = "SERVICE_UNAVAILABLE"


def _cuentas_bloqueadas(*ids):
    return {
        cuenta.pk: cuenta
        for cuenta in Usuario.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }


def _cuenta_activa(cuenta):
    return cuenta is not None and cuenta.is_active and not cuenta.is_2fa_enabled


def _preparar_espacio_personal_legado(actor):
    if not MiembroOrganizacion.objects.filter(usuario_id=actor).exists():
        asegurar_espacio_personal(actor)


def exigir_compartida(organizacion_id):
    if not Organizacion.objects.filter(pk=organizacion_id, tipo=Organizacion.COMPARTIDO).exists():
        raise PermissionDenied(code="PLAN_FEATURE_REQUIRED")


def _exigir_plan(organizacion_id):
    try:
        leer_cuota_organizacion(organizacion_id)
    except SinSuscripcionVigente as error:
        raise PermissionDenied(code="PLAN_FEATURE_REQUIRED") from error


def _auditar(invitacion, actor, accion):
    LogAuditoria.objects.create(
        usuario_id=actor,
        organizacion_id=invitacion.organizacion_id,
        accion=accion,
        detalles={
            "version": 1, "invitacion_id": str(invitacion.pk),
            "usuario_afectado_id": str(invitacion.destinatario_usuario_id),
            "nivel_rol": invitacion.nivel_rol,
        },
    )


def _cerrar(invitacion, estado, ahora):
    invitacion.estado = estado
    invitacion.fecha_resolucion = ahora
    invitacion.save(update_fields=["estado", "fecha_resolucion"])


def _invitaciones_vigentes():
    return Invitacion.objects.filter(
        estado=Invitacion.PENDIENTE, fecha_expiracion__gt=timezone.now(),
    ).order_by("fecha_creacion", "id")


def pendientes_recibidas(actor):
    return _invitaciones_vigentes().filter(destinatario_usuario_id=actor).select_related("organizacion")


def pendientes_enviadas(usuario, organizacion_id):
    autorizar_organizacion(usuario, organizacion_id, AccionOrganizacion.LISTAR_INVITACIONES)
    exigir_compartida(organizacion_id)
    return _invitaciones_vigentes().filter(
        organizacion_id=organizacion_id,
    ).select_related("destinatario_usuario")


def enviar_invitacion(actor, organizacion_id, correo, rol):
    repo = RepositorioMiembros()
    with repo.transaccion(organizacion_id):
        # Verificar el ámbito antes de buscar cuentas por correo.
        if not MiembroOrganizacion.objects.filter(usuario_id=actor, organizacion_id=organizacion_id).exists():
            raise NotFound()
        if not MiembroOrganizacion.objects.filter(usuario_id=actor, organizacion_id=organizacion_id, nivel_rol=0).exists():
            raise PermissionDenied()
        candidatas = list(Usuario.objects.filter(correo_electronico__iexact=correo).values_list("pk", flat=True)[:2])
        destinatario_id = candidatas[0] if len(candidatas) == 1 else None
        cuentas = _cuentas_bloqueadas(actor, destinatario_id) if destinatario_id else _cuentas_bloqueadas(actor)
        repo.autorizar(actor, organizacion_id)
        exigir_compartida(organizacion_id)
        _exigir_plan(organizacion_id)
        destinatario = cuentas.get(destinatario_id)
        if not _cuenta_activa(destinatario) or destinatario.correo_electronico.casefold() != correo.casefold():
            raise ValidationError({"correo_electronico": ["No se encontró una cuenta activa con ese correo."]})
        if repo.objetivo(destinatario.pk, organizacion_id) is not None:
            raise ConflictoInvitacion(code="MEMBER_EXISTS")

        ahora = timezone.now()
        pendiente = Invitacion.objects.select_for_update().filter(
            organizacion_id=organizacion_id, destinatario_usuario_id=destinatario.pk,
            estado=Invitacion.PENDIENTE,
        ).first()
        if pendiente is not None:
            if pendiente.fecha_expiracion > ahora:
                if pendiente.nivel_rol != ROLES[rol]:
                    raise ConflictoInvitacion(code="INVITATION_PENDING")
                return pendiente, False
            _cerrar(pendiente, Invitacion.VENCIDA, ahora)
            _auditar(pendiente, actor, "INVITATION_EXPIRED")

        invitacion = Invitacion.objects.create(
            organizacion_id=organizacion_id, invitado_por_id=actor,
            destinatario_usuario_id=destinatario.pk, nivel_rol=ROLES[rol],
            fecha_creacion=ahora, fecha_expiracion=ahora + VIGENCIA,
        )
        _auditar(invitacion, actor, "INVITATION_CREATED")
        return invitacion, True


def decidir_invitacion(actor, invitacion_id, decision):
    if decision not in (Invitacion.ACEPTADA, Invitacion.RECHAZADA):
        raise ValidationError({"decision": ["La decisión no es válida."]})
    recibida = Invitacion.objects.filter(pk=invitacion_id, destinatario_usuario_id=actor)
    organizacion_id = recibida.values_list("organizacion_id", flat=True).first()
    if organizacion_id is None:
        raise NotFound()

    repo = RepositorioMiembros()
    with repo.transaccion(organizacion_id):
        invitacion = recibida.select_for_update().filter(organizacion_id=organizacion_id).first()
        if invitacion is None:
            raise NotFound()
        cuentas = _cuentas_bloqueadas(actor, invitacion.invitado_por_id)
        if not _cuenta_activa(cuentas.get(actor)):
            raise PermissionDenied()
        if invitacion.estado == decision:
            return invitacion
        ahora = timezone.now()
        if invitacion.estado != Invitacion.PENDIENTE or invitacion.fecha_expiracion <= ahora:
            raise ConflictoInvitacion(code="INVITATION_CLOSED")
        if decision == Invitacion.ACEPTADA:
            exigir_compartida(organizacion_id)
            _exigir_plan(organizacion_id)
            repo.autorizar(invitacion.invitado_por_id, organizacion_id)
            if repo.objetivo(actor, organizacion_id) is not None:
                raise ConflictoInvitacion(code="MEMBER_EXISTS")
            _preparar_espacio_personal_legado(actor)
            ahora = timezone.now()
            if invitacion.fecha_expiracion <= ahora:
                raise ConflictoInvitacion(code="INVITATION_CLOSED")
            MiembroOrganizacion.objects.create(
                organizacion_id=organizacion_id, usuario_id=actor,
                nivel_rol=invitacion.nivel_rol, fecha_union=ahora,
            )
        _cerrar(invitacion, decision, ahora)
        _auditar(invitacion, actor, "INVITATION_ACCEPTED" if decision == Invitacion.ACEPTADA else "INVITATION_REJECTED")
        return invitacion


def revocar_invitacion(actor, organizacion_id, invitacion_id):
    repo = RepositorioMiembros()
    with repo.transaccion(organizacion_id):
        repo.autorizar(actor, organizacion_id)
        invitacion = Invitacion.objects.select_for_update().filter(pk=invitacion_id, organizacion_id=organizacion_id).first()
        if invitacion is None:
            raise NotFound()
        if invitacion.estado == Invitacion.REVOCADA:
            return
        ahora = timezone.now()
        if invitacion.estado != Invitacion.PENDIENTE or invitacion.fecha_expiracion <= ahora:
            raise ConflictoInvitacion(code="INVITATION_CLOSED")
        _cerrar(invitacion, Invitacion.REVOCADA, ahora)
        _auditar(invitacion, actor, "INVITATION_REVOKED")


def crear_organizacion_compartida(actor, organizacion_id, nombre):
    repo = RepositorioMiembros()
    with repo.transaccion(organizacion_id):
        cuenta = _cuentas_bloqueadas(actor).get(actor)
        if not _cuenta_activa(cuenta):
            raise PermissionDenied()
        existente = Organizacion.objects.filter(pk=organizacion_id).first()
        if existente is not None:
            repo.autorizar(actor, organizacion_id)
            if existente.tipo != Organizacion.COMPARTIDO or existente.nombre != nombre:
                raise ConflictoInvitacion(code="IDEMPOTENCY_CONFLICT")
            return False
        plan = Plan.objects.filter(pk=1, esta_activo=True, precio=0).first()
        if plan is None:
            raise InvitacionesNoDisponibles()
        _preparar_espacio_personal_legado(actor)
        crear_espacio(cuenta, nombre=nombre, tipo=Organizacion.COMPARTIDO, organizacion_id=organizacion_id, plan_id=plan.pk)
        LogAuditoria.objects.create(usuario_id=actor, organizacion_id=organizacion_id, accion="WORKSPACE_CREATED", detalles={})
        return True
