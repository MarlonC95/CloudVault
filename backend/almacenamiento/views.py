"""Rutas de almacenamiento de Dani; JWT existente y errores locales del PDF."""

from io import BytesIO

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import MethodNotAllowed, ParseError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_workspaces.authentication import CloudVaultJWTAuthentication

from .configuracion_inicio import (
    cliente_firmador, entero_configurado, maximo_publicacion, politica_inicio,
    servicios_compartidos, verificador_publicacion,
)
from .confirmacion import ServicioConfirmacionCargas
from .configuracion_descarga import vigencia_descarga
from .descarga import ServicioDescargas
from .errores import error_de_almacenamiento
from .inicio import ServicioInicioCargas
from .contrato import CONFIRMAR_CARGA, DESCARGA, INICIAR_CARGA
from .openapi import documentacion_operacion
from .schema import EsquemaAlmacenamiento


class JSONInicioParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        contenido = stream.read(16385)
        if len(contenido) > 16384:
            raise ParseError("La solicitud JSON es demasiado grande.")
        return super().parse(BytesIO(contenido), media_type, parser_context)


class IniciarCargaView(APIView):
    schema = EsquemaAlmacenamiento()
    authentication_classes = [CloudVaultJWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONInicioParser]

    def get_exception_handler(self):
        def traducir(exc, context):
            if isinstance(exc, MethodNotAllowed):
                return Response({"error": {"code": "VALIDATION_ERROR",
                                           "fields": {"method": ["Usar POST para esta operación."]}}},
                                status=405)
            return error_de_almacenamiento(exc, context)
        return traducir

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(
        **documentacion_operacion(INICIAR_CARGA),
        summary="Autorizar y reservar una carga",
        description="Reserva durable antes de entregar PUT. Requiere proveedor real de destino/cuota; sin él devuelve 503.",
    )
    def post(self, request):
        servicio = ServicioInicioCargas(
            servicios_factory=servicios_compartidos, firmador_factory=cliente_firmador,
            politica=politica_inicio(),
            limite_inicios=entero_configurado("ALMACENAMIENTO_INICIOS_POR_VENTANA", 10),
            ventana_segundos=entero_configurado("ALMACENAMIENTO_VENTANA_INICIOS_SEGUNDOS", 60),
        )
        datos = servicio.iniciar(solicitante_id=request.user.pk, datos=request.data)
        return Response(datos, status=201)


class ConfirmarCargaView(IniciarCargaView):
    @extend_schema(
        **documentacion_operacion(CONFIRMAR_CARGA),
        summary="Verificar y confirmar una carga",
        description="COPY una vez, hash final en proceso acotado y metadatos atómicos. Requiere proveedor real; sin él 503.",
    )
    def post(self, request, id):
        servicio = ServicioConfirmacionCargas(
            servicios_factory=servicios_compartidos, cliente_factory=cliente_firmador,
            verificador=verificador_publicacion(), maximo_bytes=maximo_publicacion())
        datos = servicio.confirmar(solicitante_id=request.user.pk, archivo_id=id, datos=request.data)
        return Response(datos, status=200)


class DescargaView(IniciarCargaView):
    http_method_names = ["get", "options"]

    def get_exception_handler(self):
        def traducir(exc, context):
            if isinstance(exc, MethodNotAllowed):
                return Response({"error": {"code": "VALIDATION_ERROR",
                                           "fields": {"method": ["Usar GET para esta operación."]}}},
                                status=405)
            return error_de_almacenamiento(exc, context)
        return traducir

    @extend_schema(
        **documentacion_operacion(DESCARGA),
        summary="Obtener descarga temporal autorizada",
        description="Reautoriza archivo confirmado y emite GET firmado como adjunto. Requiere proveedor real; sin él 503.",
    )
    def get(self, request, id):
        if request.query_params:
            raise ParseError("La descarga no admite parámetros de consulta.")
        stream = request.stream
        if stream is not None and stream.read(1):
            raise ParseError("La descarga no admite cuerpo de solicitud.")
        servicio = ServicioDescargas(
            servicios_factory=servicios_compartidos, cliente_factory=cliente_firmador,
            vigencia=vigencia_descarga(),
            limite=entero_configurado("ALMACENAMIENTO_DESCARGAS_POR_VENTANA", 30),
            ventana_segundos=entero_configurado("ALMACENAMIENTO_VENTANA_DESCARGAS_SEGUNDOS", 60))
        datos = servicio.descargar(solicitante_id=request.user.pk, archivo_id=id)
        return Response(datos, status=200)
