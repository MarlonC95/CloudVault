"""Verify a stored Django password and issue a session for eligible users."""

from django.contrib.auth.hashers import check_password, make_password
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Usuario


class CredencialesInvalidas(APIException):
    status_code = 401
    default_detail = "Correo o contraseña incorrectos"
    default_code = "INVALID_CREDENTIALS"


# Run the same password hasher for an unknown email to reduce timing disclosure.
_DUMMY_PASSWORD_HASH = make_password("clave ficticia solo para comprobación")


def iniciar_sesion(correo, contrasena):
    usuario = Usuario.objects.filter(correo_electronico__iexact=correo).first()
    contrasena_hash = usuario.password if usuario else _DUMMY_PASSWORD_HASH
    contrasena_correcta = check_password(contrasena, contrasena_hash)

    if (
        not usuario
        or not contrasena_correcta
        or not usuario.is_active
        or usuario.is_2fa_enabled
    ):
        raise CredencialesInvalidas()

    refresh = RefreshToken.for_user(usuario)
    return usuario, {"access": str(refresh.access_token), "refresh": str(refresh)}
