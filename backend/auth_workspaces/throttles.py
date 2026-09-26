"""Registration attempt limits."""

from hashlib import sha256

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class RegistroIPThrottle(SimpleRateThrottle):
    scope = "registro_ip"

    def get_rate(self):
        return settings.REGISTRATION_IP_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RegistroCorreoThrottle(SimpleRateThrottle):
    scope = "registro_correo"

    def get_rate(self):
        return settings.REGISTRATION_EMAIL_RATE

    def get_cache_key(self, request, view):
        if not isinstance(request.data, dict):
            return None
        correo = request.data.get("correo_electronico")
        if not isinstance(correo, str) or not correo.strip():
            return None
        key = sha256(correo.strip().lower().encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": key}


class LoginIPThrottle(SimpleRateThrottle):
    scope = "login_ip"

    def get_rate(self):
        return settings.LOGIN_IP_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginCorreoThrottle(SimpleRateThrottle):
    scope = "login_correo"

    def get_rate(self):
        return settings.LOGIN_EMAIL_RATE

    def get_cache_key(self, request, view):
        if not isinstance(request.data, dict):
            return None
        correo = request.data.get("correo")
        if not isinstance(correo, str) or not correo.strip():
            return None
        key = sha256(correo.strip().lower().encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": key}


class RecuperacionIPThrottle(SimpleRateThrottle):
    scope = "recuperacion_ip"

    def get_rate(self):
        return settings.RECOVERY_IP_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RecuperacionCorreoThrottle(SimpleRateThrottle):
    scope = "recuperacion_correo"

    def get_rate(self):
        return settings.RECOVERY_EMAIL_RATE

    def get_cache_key(self, request, view):
        if not isinstance(request.data, dict):
            return None
        correo = request.data.get("correo")
        if not isinstance(correo, str) or not correo.strip():
            return None
        key = sha256(correo.strip().lower().encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": key}
