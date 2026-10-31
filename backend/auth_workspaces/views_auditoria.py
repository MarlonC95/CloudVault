"""Auditoría organizacional restringida al propietario vigente."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.views import APIView

from .auditoria_organizaciones import consultar_auditoria_organizacion
from .authentication import CloudVaultJWTAuthentication
from .contratos_auditoria import fecha_utc, filtros_auditoria
from .errores_organizaciones import error_de_organizaciones


def _enlace(request, filtros, page):
    if page is None:
        return None
    url = request.build_absolute_uri()
    # Materializar fechas por defecto y el corte en los enlaces impide que
    # nuevas lecturas incluyan el evento propio o cambien la ventana temporal.
    valores = {
        "page": page, "page_size": filtros.page_size,
        "desde": fecha_utc(filtros.desde), "hasta": fecha_utc(filtros.fin_lectura),
    }
    if filtros.usuario_id is not None:
        valores["usuario_id"] = str(filtros.usuario_id)
    if filtros.accion is not None:
        valores["accion"] = filtros.accion
    for nombre, valor in valores.items():
        url = replace_query_param(url, nombre, valor)
    return url


class AuditoriaOrganizacionView(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]

    def get_exception_handler(self):
        return error_de_organizaciones

    def get(self, request, organizacion_id):
        if request.body:
            raise ValidationError({"non_field_errors": ["Esta consulta no admite cuerpo."]})
        filtros = filtros_auditoria(request.query_params, corte=timezone.now())
        pagina = consultar_auditoria_organizacion(request.user, organizacion_id, filtros)
        siguiente = filtros.page + 1 if filtros.page * filtros.page_size < pagina.count else None
        anterior = filtros.page - 1 if filtros.page > 1 else None
        return Response({
            "count": pagina.count, "page_size": filtros.page_size,
            "next": _enlace(request, filtros, siguiente),
            "previous": _enlace(request, filtros, anterior),
            "results": pagina.results,
        })
