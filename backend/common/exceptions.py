from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler

from .responses import fail


def api_exception_handler(exc, context):
    """Traduce errores DRF al formato de error del contrato (§0.3/§0.4)."""
    if isinstance(exc, Http404) or isinstance(exc, exceptions.NotFound):
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
        detail = exc.detail
        fields = detail if isinstance(detail, dict) else {"non_field_errors": detail}
        return fail("VALIDATION_ERROR", fields, status=400)
    return exception_handler(exc, context)
