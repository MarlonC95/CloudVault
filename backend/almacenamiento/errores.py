"""Adaptación local al catálogo del PDF, sin cambiar autenticación existente."""

import logging
from math import ceil

from django.db import OperationalError
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import set_rollback

from .contrato import CodigoError, ESTADOS_HTTP_ERROR


logger = logging.getLogger(__name__)


class ErrorCarga(APIException):
    def __init__(self, codigo, *, fields=None):
        self.codigo = CodigoError(codigo)
        self.status_code = ESTADOS_HTTP_ERROR[self.codigo]
        self.fields = fields or {}
        super().__init__(detail="La operación de carga no pudo completarse.")


def _campos_validacion(detail):
    if not isinstance(detail, dict):
        detail = {"non_field_errors": detail}
    return {
        str(campo): [str(item) for item in (valor if isinstance(valor, list) else [valor])]
        for campo, valor in detail.items()
    }


def error_de_almacenamiento(exc, context=None):
    """Handler local de Dani; context conserva la firma (exc, context) de DRF.

    No se instala globalmente ni necesita el contexto para construir el error.
    """
    fields = {}
    headers = {}
    if isinstance(exc, ErrorCarga):
        codigo, fields = exc.codigo, exc.fields
    elif isinstance(exc, ValidationError):
        codigo, fields = CodigoError.VALIDATION_ERROR, _campos_validacion(exc.detail)
    elif isinstance(exc, (ParseError, UnsupportedMediaType)):
        codigo = CodigoError.VALIDATION_ERROR
        fields = {"non_field_errors": ["Se requiere un objeto JSON válido."]}
    elif isinstance(exc, NotAuthenticated):
        codigo = CodigoError.NO_AUTENTICADO
    elif isinstance(exc, AuthenticationFailed):
        codigo = CodigoError.TOKEN_INVALIDO
    elif isinstance(exc, PermissionDenied):
        codigo = CodigoError.SIN_PERMISO
    elif isinstance(exc, NotFound):
        codigo = CodigoError.NO_ENCONTRADO
    elif isinstance(exc, Throttled):
        codigo = CodigoError.RATE_LIMITED
        if exc.wait is not None:
            headers["Retry-After"] = str(ceil(exc.wait))
    elif isinstance(exc, OperationalError):
        codigo = CodigoError.SERVICE_UNAVAILABLE
    else:
        codigo = CodigoError.ERROR_INTERNO
        logger.error("Error de almacenamiento no controlado (%s)", type(exc).__name__)
    if ESTADOS_HTTP_ERROR[codigo] == 401:
        headers["WWW-Authenticate"] = "Bearer"
    set_rollback()
    return Response(
        {"error": {"code": codigo.value, "fields": fields}},
        status=ESTADOS_HTTP_ERROR[codigo],
        headers=headers,
    )
