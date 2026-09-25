"""Stable error envelope for the public API."""

import logging

from django.db import OperationalError
from rest_framework.exceptions import (
    APIException,
    ParseError,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .login import CredencialesInvalidas
from .recovery import DatosRecuperacionInvalidos
from .services import CorreoEnUso


logger = logging.getLogger(__name__)


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Servicio temporalmente no disponible."
    default_code = "SERVICE_UNAVAILABLE"


def api_exception_handler(exc, context):
    if isinstance(exc, OperationalError):
        exc = ServiceUnavailable()
    response = exception_handler(exc, context)
    if response is None:
        # Exception messages and traceback locals may contain JSON credentials.
        # Keep the API response and log safe even during local debugging.
        set_rollback()
        logger.error("Unhandled API exception (%s)", type(exc).__name__)
        return Response(
            {"error": {"code": "INTERNAL_ERROR", "message": "Ocurrió un error interno."}},
            status=500,
        )

    if isinstance(exc, ValidationError):
        code, message = "VALIDATION_ERROR", "Revisa los datos enviados."
        if isinstance(response.data, dict):
            fields = {
                name: [str(item) for item in (items if isinstance(items, list) else [items])]
                for name, items in response.data.items()
            }
        else:
            fields = {"non_field_errors": [str(item) for item in response.data]}
        body = {"code": code, "message": message, "fields": fields}
    elif isinstance(exc, ParseError):
        body = {"code": "INVALID_JSON", "message": "El JSON no es válido."}
    elif isinstance(exc, UnsupportedMediaType):
        body = {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Se requiere JSON."}
    elif isinstance(exc, Throttled):
        body = {"code": "RATE_LIMITED", "message": "Demasiados intentos."}
    elif isinstance(exc, CredencialesInvalidas):
        body = {"code": "INVALID_CREDENTIALS", "message": str(exc.detail)}
    elif isinstance(exc, DatosRecuperacionInvalidos):
        body = {"code": "RECOVERY_VERIFICATION_FAILED", "message": str(exc.detail)}
    elif isinstance(exc, CorreoEnUso):
        body = {"code": "CORREO_EN_USO", "message": str(exc.detail)}
    elif isinstance(exc, ServiceUnavailable):
        body = {"code": "SERVICE_UNAVAILABLE", "message": str(exc.detail)}
    else:
        body = {"code": exc.get_codes() if hasattr(exc, "get_codes") else "API_ERROR", "message": str(exc.detail)}

    response.data = {"error": body}
    return response
