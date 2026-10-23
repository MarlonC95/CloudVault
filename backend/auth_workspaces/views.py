"""Public registration and authenticated profile endpoints."""

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import OperationalError
from django.http import JsonResponse
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.ambito import resolver_organizacion
from common.errores import ContratoAPIMixin
from common.responses import fail, ok

from .exceptions import ServiceUnavailable
from .login import iniciar_sesion
from .recovery import recuperar_contrasena
from .serializers import (
    CambiarContrasenaSerializer,
    LoginInputSerializer,
    LoginSuccessSerializer,
    LogoutInputSerializer,
    PerfilPatchSerializer,
    RecuperarContrasenaInputSerializer,
    RecuperarContrasenaSuccessSerializer,
    RegistroErrorSerializer,
    RegistroInputSerializer,
    RegistroSuccessSerializer,
    RegistroUsuarioSerializer,
    RotatingTokenRefreshSerializer,
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


_ROL_A_TEXTO = {0: "admin", 1: "lector", 2: "operativo", 3: "avanzado"}


def _perfil_publico(usuario, ambito):
    # Imports diferidos: auth no debe cargar subscriptions al importarse (config.urls importa este módulo).
    from subscriptions import services as subscription_services
    from subscriptions.cuotas import SinSuscripcionVigente, leer_cuota_organizacion
    from subscriptions.models import Suscripcion

    plan = None
    almacenamiento = {
        "usado_bytes": 0,
        "cuota_bytes": 0,
        "usado_legible": "0 B",
        "cuota_legible": "0 B",
        "porcentaje_usado": 0,
    }
    if ambito is not None:
        try:
            limite, usado, _ = leer_cuota_organizacion(ambito.organizacion_id)
            almacenamiento = subscription_services.bloque_almacenamiento(usado, limite)
        except SinSuscripcionVigente:
            pass
        suscripcion = (
            Suscripcion.objects.select_related("plan")
            .filter(organizacion_id=ambito.organizacion_id, estado=Suscripcion.ESTADO_ACTIVE)
            .order_by("-periodo_inicio")
            .first()
        )
        if suscripcion is not None:
            plan = {
                "id": subscription_services.id_publico(suscripcion.plan_id),
                "nombre": subscription_services.nombre_mostrado(suscripcion.plan.nombre),
            }

    return {
        "id": str(usuario.id),
        "nombre_completo": usuario.nombre_completo,
        "correo_electronico": usuario.correo_electronico,
        "rol": _ROL_A_TEXTO.get(ambito.nivel_rol if ambito else 0, "admin"),
        "plan": plan,
        "dos_factores": usuario.is_2fa_enabled,
        "almacenamiento": almacenamiento,
        "fecha_registro": subscription_services.fecha_iso(usuario.date_joined),
    }


class RegistroView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [RegistroIPThrottle, RegistroCorreoThrottle]

    @extend_schema(
        summary="Registrar usuario",
        description="Crea la identidad del usuario y su espacio personal con plan gratuito.",
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


class RefreshView(ContratoAPIMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Renovar access token",
        description="Rota el refresh token y devuelve un nuevo par de tokens JWT.",
        request=inline_serializer(
            "RefreshEntrada", fields={"refresh": serializers.CharField()}
        ),
        responses={200: OpenApiResponse(description="Nuevos tokens JWT.")},
        tags=["Usuarios"],
        auth=[],
    )
    def post(self, request):
        serializer = RotatingTokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            return fail("TOKEN_INVALIDO", status=401)
        return ok(serializer.validated_data)


class LogoutView(ContratoAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cerrar sesión",
        description="Acepta el refresh token y confirma el cierre de sesión.",
        request=LogoutInputSerializer,
        responses={200: OpenApiResponse(description="Sesión cerrada.")},
        tags=["Usuarios"],
    )
    def post(self, request):
        serializer = LogoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return ok({"mensaje": "Sesión cerrada correctamente."})


class PerfilView(ContratoAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Perfil de usuario",
        description="Devuelve o actualiza el perfil, incluyendo plan y almacenamiento.",
        request=PerfilPatchSerializer,
        responses={200: OpenApiResponse(description="Perfil de usuario.")},
        tags=["Usuarios"],
    )
    def get(self, request):
        ambito = self._resolver_ambito(request.user)
        return ok(_perfil_publico(request.user, ambito))

    def patch(self, request):
        serializer = PerfilPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = request.user
        campos = []
        if "nombre_completo" in serializer.validated_data:
            usuario.nombre_completo = serializer.validated_data["nombre_completo"]
            campos.append("nombre_completo")
        if "correo_electronico" in serializer.validated_data:
            nuevo_correo = serializer.validated_data["correo_electronico"]
            if nuevo_correo != usuario.correo_electronico:
                if (
                    type(usuario)
                    .objects.filter(correo_electronico__iexact=nuevo_correo)
                    .exclude(pk=usuario.pk)
                    .exists()
                ):
                    return fail("CORREO_EN_USO", status=409)
                usuario.correo_electronico = nuevo_correo
                campos.append("correo_electronico")
        if campos:
            usuario.save(update_fields=campos)
        return ok({
            "id": str(usuario.id),
            "nombre_completo": usuario.nombre_completo,
            "correo_electronico": usuario.correo_electronico,
        })

    def _resolver_ambito(self, usuario):
        try:
            return resolver_organizacion(usuario)
        except Exception:
            return None


class CambiarContrasenaView(ContratoAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cambiar contraseña",
        description="Cambia la contraseña validando la contraseña actual.",
        request=CambiarContrasenaSerializer,
        responses={200: OpenApiResponse(description="Contraseña actualizada.")},
        tags=["Usuarios"],
    )
    def post(self, request):
        serializer = CambiarContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = request.user
        if not check_password(serializer.validated_data["contrasena_actual"], usuario.password):
            raise ValidationError(
                {"contrasena_actual": ["La contraseña actual no es correcta."]}
            )

        nueva = serializer.validated_data["nueva_contrasena"]
        try:
            validate_password(nueva, user=usuario)
        except DjangoValidationError as exc:
            raise ValidationError({"nueva_contrasena": exc.messages}) from exc

        usuario.password = make_password(nueva)
        usuario.save(update_fields=["password"])
        return ok({"mensaje": "La contraseña se actualizó correctamente."})


def server_error(request):
    return JsonResponse(
        {"error": {"code": "INTERNAL_ERROR", "message": "Ocurrió un error interno."}},
        status=500,
    )
