"""Rutas del flujo interno de invitaciones y creación de espacios compartidos."""

from collections.abc import Mapping

from django.db import ProgrammingError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from common.pagination import EnvelopePagination
from common.responses import ok

from . import invitaciones
from .authentication import CloudVaultJWTAuthentication
from .errores_organizaciones import error_de_organizaciones
from .gestion_miembros import ROLES
from .models import InvitacionOrganizacion
from .permisos_administracion import _cuenta_vigente

ROLES_PUBLICOS = {nivel: rol for rol, nivel in ROLES.items()}


class EntradaEstricta(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) - self.fields.keys():
            raise ValidationError({"non_field_errors": ["El cuerpo contiene campos no admitidos."]})
        return super().to_internal_value(data)


class EntradaInvitar(EntradaEstricta):
    correo_electronico = serializers.EmailField(max_length=255)
    rol = serializers.ChoiceField(choices=tuple(ROLES))


class EntradaDecision(EntradaEstricta):
    decision = serializers.ChoiceField(choices=("ACEPTAR", "RECHAZAR"))


class EntradaOrganizacion(EntradaEstricta):
    id = serializers.UUIDField()
    nombre = serializers.CharField(max_length=150, trim_whitespace=True)


def _error(exc, context):
    if isinstance(exc, invitaciones.ConflictoInvitacion):
        return Response({"error": {"code": exc.get_codes()}}, status=409)
    if isinstance(exc, PermissionDenied) and exc.get_codes() == "PLAN_FEATURE_REQUIRED":
        return Response({"error": {"code": "PLAN_FEATURE_REQUIRED"}}, status=403)
    if isinstance(exc, invitaciones.InvitacionesNoDisponibles) or (
        isinstance(exc, ProgrammingError)
        and getattr(exc.__cause__, "sqlstate", None) in ("42P01", "42703")
    ):
        return Response({"error": {"code": "SERVICE_UNAVAILABLE"}}, status=503)
    return error_de_organizaciones(exc, context)


def _fila(invitacion):
    return {
        "id": str(invitacion.pk), "organizacion_id": str(invitacion.organizacion_id),
        "rol": ROLES_PUBLICOS[invitacion.nivel_rol], "estado": invitacion.estado,
        "fecha_creacion": invitacion.fecha_creacion, "fecha_expiracion": invitacion.fecha_expiracion,
    }


class LimiteInvitacion(SimpleRateThrottle):
    scope = "invitacion_organizacion"

    def get_rate(self):
        return "20/hour"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"{request.user.pk}:{view.kwargs['organizacion_id']}"}


class LimiteCreacion(SimpleRateThrottle):
    scope = "organizacion_compartida"

    def get_rate(self):
        return "10/hour"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class BaseInvitacionesView(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_exception_handler(self):
        return _error

    def finalize_response(self, request, response, *args, **kwargs):
        respuesta = super().finalize_response(request, response, *args, **kwargs)
        respuesta["Cache-Control"] = "no-store"
        return respuesta

    def paginar(self, request, consulta, proyectar):
        if request.body:
            raise ValidationError({"non_field_errors": ["Esta consulta no admite cuerpo."]})
        paginador = EnvelopePagination()
        pagina = paginador.paginate_queryset(consulta, request, view=self)
        return paginador.get_paginated_response([proyectar(fila) for fila in pagina])


class InvitarMiembroView(BaseInvitacionesView):
    throttle_classes = [LimiteInvitacion]

    def post(self, request, organizacion_id):
        entrada = EntradaInvitar(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        invitacion, creada = invitaciones.enviar_invitacion(
            request.user.pk, organizacion_id, datos["correo_electronico"].lower(), datos["rol"],
        )
        return ok(_fila(invitacion), status=201 if creada else 200)


class InvitacionesEnviadasView(BaseInvitacionesView):
    def get(self, request, organizacion_id):
        consulta = invitaciones.pendientes_enviadas(request.user, organizacion_id)
        return self.paginar(request, consulta, lambda invitacion: {
            **_fila(invitacion), "correo_electronico": invitacion.destinatario_usuario.correo_electronico,
        })


class InvitacionesRecibidasView(BaseInvitacionesView):
    def get(self, request):
        actor = _cuenta_vigente(request.user)
        return self.paginar(request, invitaciones.pendientes_recibidas(actor.pk), lambda invitacion: {
            **_fila(invitacion), "organizacion_nombre": invitacion.organizacion.nombre,
        })


class DecisionInvitacionView(BaseInvitacionesView):
    def post(self, request, invitacion_id):
        entrada = EntradaDecision(data=request.data)
        entrada.is_valid(raise_exception=True)
        decision = (
            InvitacionOrganizacion.ACEPTADA if entrada.validated_data["decision"] == "ACEPTAR"
            else InvitacionOrganizacion.RECHAZADA
        )
        invitacion = invitaciones.decidir_invitacion(request.user.pk, invitacion_id, decision)
        return ok(_fila(invitacion))


class RevocarInvitacionView(BaseInvitacionesView):
    def delete(self, request, organizacion_id, invitacion_id):
        if request.body:
            raise ValidationError({"non_field_errors": ["Esta operación no admite cuerpo."]})
        invitaciones.revocar_invitacion(request.user.pk, organizacion_id, invitacion_id)
        return Response(status=204)


class CrearCompartidaView(BaseInvitacionesView):
    throttle_classes = [LimiteCreacion]

    def post(self, request):
        entrada = EntradaOrganizacion(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        creada = invitaciones.crear_organizacion_compartida(request.user.pk, datos["id"], datos["nombre"])
        return ok({"id": str(datos["id"]), "nombre": datos["nombre"], "tipo": "COMPARTIDO"}, status=201 if creada else 200)
