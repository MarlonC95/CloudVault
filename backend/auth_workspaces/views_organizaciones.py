"""Lectura paginada de miembros con pertenencia vigente."""

import re

from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.views import APIView

from .authentication import CloudVaultJWTAuthentication
from .errores_organizaciones import error_de_organizaciones
from .organizaciones import listar_miembros
from .permisos_administracion import AccionOrganizacion, autorizar_organizacion
from .serializers_organizaciones import MiembroOrganizacionSerializer


def _paginacion(request):
    if request.body:
        raise ValidationError({"non_field_errors": ["Esta consulta no admite cuerpo."]})
    errores = {}
    valores = {"page": 1, "page_size": 50}
    for nombre in request.query_params:
        items = request.query_params.getlist(nombre)
        if nombre not in valores:
            errores[nombre] = ["Este parámetro no está permitido."]
        elif len(items) != 1:
            errores[nombre] = ["El parámetro no puede repetirse."]
        elif not re.fullmatch(r"[0-9]+", items[0]):
            errores[nombre] = ["Debe ser un entero decimal positivo."]
        else:
            try:
                valor = int(items[0])
            except ValueError:
                errores[nombre] = ["El valor está fuera del rango permitido."]
                continue
            if valor < 1 or (nombre == "page_size" and valor > 100):
                errores[nombre] = ["El valor está fuera del rango permitido."]
            else:
                valores[nombre] = valor
    if errores:
        raise ValidationError(errores)
    return valores


def _enlace(request, pagina, tamano):
    if pagina is None:
        return None
    url = replace_query_param(request.build_absolute_uri(), "page_size", tamano)
    return replace_query_param(url, "page", pagina)


class MiembrosOrganizacionView(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["get"]

    def get_exception_handler(self):
        return error_de_organizaciones

    def get(self, request, organizacion_id):
        paginacion = _paginacion(request)
        ambito = autorizar_organizacion(
            request.user, organizacion_id, AccionOrganizacion.LISTAR_MIEMBROS,
        )
        pagina = listar_miembros(ambito.organizacion_id, **paginacion)
        siguiente = pagina.page + 1 if pagina.page * pagina.page_size < pagina.count else None
        anterior = pagina.page - 1 if pagina.page > 1 else None
        return Response({
            "count": pagina.count,
            "next": _enlace(request, siguiente, pagina.page_size),
            "previous": _enlace(request, anterior, pagina.page_size),
            "page_size": pagina.page_size,
            "results": MiembroOrganizacionSerializer(pagina.results, many=True).data,
        })


class GestionMiembroView(APIView):
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ["patch", "delete"]

    def get_exception_handler(self):
        return error_de_organizaciones

    def _ejecutar(self, request, organizacion_id, usuario_id, retirar):
        from collections.abc import Mapping
        from .gestion_miembros import ServicioMiembros
        if request.query_params:
            raise ValidationError({"non_field_errors": ["Esta operación no admite parámetros de consulta."]})
        datos = request.data
        if not isinstance(datos, Mapping) or (set(datos) if retirar else set(datos) - {"rol"}):
            raise ValidationError({"non_field_errors": ["Solo se admite rol en PATCH y cuerpo vacío en DELETE."]})
        ServicioMiembros().ejecutar(request.user.pk, organizacion_id, usuario_id,
            retirar=retirar, rol=datos.get("rol"))
        return Response({"mensaje": "Miembro removido de la organización." if retirar else "Rol de usuario actualizado exitosamente."})

    def patch(self, request, organizacion_id, usuario_id):
        return self._ejecutar(request, organizacion_id, usuario_id, False)

    def delete(self, request, organizacion_id, usuario_id):
        return self._ejecutar(request, organizacion_id, usuario_id, True)
