"""Manejo de errores del contrato (§0.3/§0.4) aplicable por vista.

No reemplaza el handler global de ``auth_workspaces``: se activa solo en las vistas que
usan ``ContratoAPIMixin``.
"""

from django.db import OperationalError
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler, set_rollback

from .responses import fail


def _campos(detail):
    if isinstance(detail, dict):
        return {
            nombre: [str(i) for i in (items if isinstance(items, (list, tuple)) else [items])]
            for nombre, items in detail.items()
        }
    items = detail if isinstance(detail, (list, tuple)) else [detail]
    return {"non_field_errors": [str(i) for i in items]}


def manejar_error(exc, context):
    if isinstance(exc, OperationalError):
        set_rollback()
        return fail("SERVICE_UNAVAILABLE", status=503)
    if isinstance(exc, (Http404, exceptions.NotFound)):
        return fail("NO_ENCONTRADO", status=404)
    if isinstance(exc, exceptions.NotAuthenticated):
        return fail("NO_AUTENTICADO", status=401)
    if isinstance(exc, exceptions.AuthenticationFailed):
        return fail("TOKEN_INVALIDO", status=401)
    if isinstance(exc, exceptions.PermissionDenied):
        return fail("SIN_PERMISO", status=403)
    if isinstance(exc, exceptions.Throttled):
        return fail("RATE_LIMITED", status=429)
    if isinstance(exc, exceptions.ValidationError):
        return fail("VALIDATION_ERROR", _campos(exc.detail), status=400)
    if isinstance(exc, exceptions.ParseError):
        return fail("VALIDATION_ERROR", {"non_field_errors": [str(exc.detail)]}, status=400)
    if isinstance(exc, exceptions.MethodNotAllowed):
        return fail("METODO_NO_PERMITIDO", status=405)
    return exception_handler(exc, context)


class ContratoAPIMixin:
    """Mezclar en APIView/ViewSet para devolver errores en el formato del contrato."""

    def get_exception_handler(self):
        return manejar_error
