"""JWT authentication aligned with the current account eligibility rules."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class CloudVaultJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        usuario = super().get_user(validated_token)
        if usuario.is_2fa_enabled:
            raise AuthenticationFailed("La sesión no está disponible.")
        return usuario
