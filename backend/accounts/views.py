from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


def error(code, fields=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {"error": {"code": code}}
    if fields:
        payload["error"]["fields"] = fields
    return Response(payload, status=http_status)


def texto(data, key):
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    name = texto(request.data, "nombre_completo")
    email = texto(request.data, "correo_electronico").lower()
    password = request.data.get("contrasena", "")
    phrase = texto(request.data, "palabra_secreta")
    fields = {}
    if not name or len(name) > 150:
        fields["nombre_completo"] = ["Ingresa un nombre de hasta 150 caracteres."]
    if not email or len(email) > 255 or "@" not in email:
        fields["correo_electronico"] = ["Ingresa un correo electrónico válido."]
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        fields["contrasena"] = ["La contraseña debe tener entre 8 y 128 caracteres."]
    if not phrase or len(phrase) < 12 or len(phrase) > 128:
        fields["palabra_secreta"] = ["La frase debe tener entre 12 y 128 caracteres."]
    if fields:
        return error("VALIDATION_ERROR", fields)
    if User.objects.filter(email=email).exists():
        return error("CORREO_EN_USO", http_status=status.HTTP_409_CONFLICT)
    try:
        password_validation.validate_password(password)
    except ValidationError as exc:
        return error("VALIDATION_ERROR", {"contrasena": list(exc.messages)})
    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=name,
        recovery_phrase=make_password(phrase),
    )
    return Response({"data": {
        "id": str(user.pk),
        "nombre_completo": user.full_name,
        "correo_electronico": user.email,
    }}, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    email = texto(request.data, "correo").lower()
    password = request.data.get("contrasena", "")
    if not email or not isinstance(password, str) or not password:
        return error("VALIDATION_ERROR", {"correo": ["Ingresa correo y contraseña."]})
    user = authenticate(request, email=email, password=password)
    if user is None:
        return error("INVALID_CREDENTIALS", http_status=status.HTTP_401_UNAUTHORIZED)
    refresh = RefreshToken.for_user(user)
    return Response({"data": {
        "usuario": {
            "id": str(user.pk),
            "nombre_completo": user.full_name,
            "correo_electronico": user.email,
        },
        "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
    }})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def recover_password(request):
    email = texto(request.data, "correo").lower()
    phrase = texto(request.data, "palabra_secreta")
    password = request.data.get("nueva_contrasena", "")
    confirmation = request.data.get("confirmar_contrasena", "")
    fields = {}
    if not email:
        fields["correo"] = ["El correo es obligatorio."]
    if not phrase:
        fields["palabra_secreta"] = ["La frase secreta es obligatoria."]
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        fields["nueva_contrasena"] = ["La contraseña debe tener entre 8 y 128 caracteres."]
    if password != confirmation:
        fields["confirmar_contrasena"] = ["Las contraseñas no coinciden."]
    if fields:
        return error("VALIDATION_ERROR", fields)
    user = User.objects.filter(email=email).first()
    if user is None or not check_password(phrase, user.recovery_phrase):
        return error("RECOVERY_VERIFICATION_FAILED", http_status=status.HTTP_400_BAD_REQUEST)
    try:
        password_validation.validate_password(password, user)
    except ValidationError as exc:
        return error("VALIDATION_ERROR", {"nueva_contrasena": list(exc.messages)})
    user.set_password(password)
    user.save(update_fields=["password"])
    return Response({"mensaje": "La contraseña se actualizó correctamente."})
