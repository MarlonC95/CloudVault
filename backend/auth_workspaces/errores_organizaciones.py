"""Contrato de errores exclusivo de las rutas nuevas de organizaciones."""

import logging

from django.db import OperationalError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .organizaciones import LecturaMiembrosNoDisponible
from .contratos_auditoria import AuditoriaNoDisponible


logger = logging.getLogger(__name__)


def error_de_organizaciones(exc, context):
    if isinstance(exc, (OperationalError, LecturaMiembrosNoDisponible, AuditoriaNoDisponible)):
        set_rollback()
        return Response({"error": {"code": "SERVICE_UNAVAILABLE"}}, status=503)
    from .gestion_miembros import PropietarioProtegido
    if isinstance(exc, PropietarioProtegido):
        set_rollback()
        return Response({"error": {"code": "OWNER_REQUIRED"}}, status=409)
    response = exception_handler(exc, context)
    if response is None:
        set_rollback()
        logger.error("Unhandled organization API exception (%s)", type(exc).__name__)
        return Response({"error": {"code": "INTERNAL_ERROR"}}, status=500)
    if isinstance(exc, exceptions.ValidationError):
        detail = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        fields = {
            nombre: [str(item) for item in (items if isinstance(items, list) else [items])]
            for nombre, items in detail.items()
        }
        response.data = {"error": {"code": "VALIDATION_ERROR", "fields": fields}}
        return response
    catalogo = (
        (exceptions.NotAuthenticated, "NO_AUTENTICADO"),
        (exceptions.AuthenticationFailed, "TOKEN_INVALID"),
        (exceptions.PermissionDenied, "FORBIDDEN"),
        ((exceptions.NotFound, Http404), "NOT_FOUND"),
        (exceptions.MethodNotAllowed, "METHOD_NOT_ALLOWED"),
        (exceptions.UnsupportedMediaType, "UNSUPPORTED_MEDIA_TYPE"),
        (exceptions.ParseError, "VALIDATION_ERROR"),
        (exceptions.Throttled, "RATE_LIMITED"),
    )
    for clase, codigo in catalogo:
        if isinstance(exc, clase):
            response.data = {"error": {"code": codigo}}
            return response
    response.data = {"error": {"code": "INTERNAL_ERROR"}}
    return response
