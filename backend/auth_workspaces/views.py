"""Public registration endpoint."""

from django.db import OperationalError
from django.http import JsonResponse
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import ServiceUnavailable
from .login import iniciar_sesion
from .recovery import recuperar_contrasena
from .serializers import (
    LoginInputSerializer,
    LoginSuccessSerializer,
    RecuperarContrasenaInputSerializer,
    RecuperarContrasenaSuccessSerializer,
    RegistroErrorSerializer,
    RegistroInputSerializer,
    RegistroSuccessSerializer,
    RegistroUsuarioSerializer,
)
from .services import registrar_usuario
from .throttles import (
    LoginCorreoThrottle,
    LoginIPThrottle,
    RecuperacionCorreoThrottle,
    RecuperacionIPThrottle,
    RegistroCorreoThrottle,
    RegistroIPThrottle,
)


class RegistroView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RegistroIPThrottle, RegistroCorreoThrottle]

    @extend_schema(
        summary="Registrar usuario",
        description="Crea únicamente la identidad del usuario; no asigna organización ni plan.",
        request=RegistroInputSerializer,
        responses={
            201: RegistroSuccessSerializer,
            400: OpenApiResponse(RegistroErrorSerializer, description="Datos inválidos"),
            409: OpenApiResponse(RegistroErrorSerializer, description="Correo en uso"),
            415: OpenApiResponse(RegistroErrorSerializer, description="Tipo de contenido inválido"),
            429: OpenApiResponse(RegistroErrorSerializer, description="Límite de intentos"),
            500: OpenApiResponse(RegistroErrorSerializer, description="Error interno"),
            503: OpenApiResponse(RegistroErrorSerializer, description="Base no disponible"),
        },
        examples=[
            OpenApiExample(
                "Solicitud de registro",
                value={
                    "nombre_completo": "Ana Pérez",
                    "correo_electronico": "Ana.Perez@Ejemplo.com",
                    "contrasena": "UnaFraseSeguraPara2026",
                    "palabra_secreta": "Recuerdo privado de hace años",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Usuario creado",
                value={
                    "data": {
                        "id": "6b3b2489-1353-4d73-a6cb-c83f741f2533",
                        "nombre_completo": "Ana Pérez",
                        "correo_electronico": "ana.perez@ejemplo.com",
                        "esta_activo": True,
                        "fecha_creacion": "2026-09-24T23:00:00Z",
                    }
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
        tags=["Usuarios"],
        auth=[],
    )
    def post(self, request):
        serializer = RegistroInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            usuario = registrar_usuario(
                serializer.validated_data, remote_addr=request.META.get("REMOTE_ADDR")
            )
        except OperationalError as exc:
            raise ServiceUnavailable() from exc
        output = RegistroUsuarioSerializer(usuario)
        return Response({"data": output.data}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginIPThrottle, LoginCorreoThrottle]

    @extend_schema(
        summary="Iniciar sesión",
        description=(
            "Recibe solo correo y contraseña. Devuelve datos públicos y tokens JWT "
            "para cuentas activas sin 2FA pendiente."
        ),
        request=LoginInputSerializer,
        responses={
            200: LoginSuccessSerializer,
            400: OpenApiResponse(RegistroErrorSerializer, description="Campos inválidos"),
            401: OpenApiResponse(RegistroErrorSerializer, description="Credenciales incorrectas"),
            415: OpenApiResponse(RegistroErrorSerializer, description="Tipo de contenido inválido"),
            429: OpenApiResponse(RegistroErrorSerializer, description="Límite de intentos"),
            503: OpenApiResponse(RegistroErrorSerializer, description="Base no disponible"),
        },
        tags=["Usuarios"],
        auth=[],
    )
    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            usuario, tokens = iniciar_sesion(**serializer.validated_data)
        except OperationalError as exc:
            raise ServiceUnavailable() from exc
        return Response(
            {"data": {"usuario": RegistroUsuarioSerializer(usuario).data, "tokens": tokens}},
            status=status.HTTP_200_OK,
        )


class RecuperarContrasenaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RecuperacionIPThrottle, RecuperacionCorreoThrottle]

    @extend_schema(
        summary="Recuperar contraseña",
        description=(
            "Verifica la palabra secreta almacenada como hash y cambia únicamente "
            "la contraseña. Una recuperación válida invalida los tokens de acceso previos."
        ),
        request=RecuperarContrasenaInputSerializer,
        responses={
            200: RecuperarContrasenaSuccessSerializer,
            400: OpenApiResponse(RegistroErrorSerializer, description="Datos inválidos"),
            401: OpenApiResponse(RegistroErrorSerializer, description="No se pudieron verificar los datos"),
            415: OpenApiResponse(RegistroErrorSerializer, description="Tipo de contenido inválido"),
            429: OpenApiResponse(RegistroErrorSerializer, description="Límite de intentos"),
            503: OpenApiResponse(RegistroErrorSerializer, description="Base no disponible"),
        },
        tags=["Usuarios"],
        auth=[],
    )
    def post(self, request):
        serializer = RecuperarContrasenaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recuperar_contrasena(
                serializer.validated_data, remote_addr=request.META.get("REMOTE_ADDR")
            )
        except OperationalError as exc:
            raise ServiceUnavailable() from exc
        return Response(
            {"mensaje": "Contraseña restablecida correctamente."},
            status=status.HTTP_200_OK,
        )


def server_error(request):
    return JsonResponse(
        {"error": {"code": "INTERNAL_ERROR", "message": "Ocurrió un error interno."}},
        status=500,
    )
