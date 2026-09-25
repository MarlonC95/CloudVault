"""Strict input and public output for the registration contract."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Usuario


class RegistroInputSerializer(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=150, trim_whitespace=True)
    correo_electronico = serializers.EmailField(max_length=255)
    contrasena = serializers.CharField(
        min_length=8, max_length=128, trim_whitespace=False, write_only=True
    )
    palabra_secreta = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Se requiere un objeto JSON."]}
            )
        extra = sorted(set(data) - set(self.fields))
        if extra:
            raise serializers.ValidationError(
                {name: ["Este campo no está permitido."] for name in extra}
            )
        invalid = {
            name: ["Debe ser una cadena de texto."]
            for name in self.fields
            if name in data and not isinstance(data[name], str)
        }
        if invalid:
            raise serializers.ValidationError(invalid)
        return super().to_internal_value(data)

    def validate_correo_electronico(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        password = attrs["contrasena"]
        secret = attrs["palabra_secreta"]
        if not password.strip():
            raise serializers.ValidationError(
                {"contrasena": ["No puede contener únicamente espacios."]}
            )
        if not secret.strip():
            raise serializers.ValidationError(
                {"palabra_secreta": ["No puede contener únicamente espacios."]}
            )
        if secret == password or secret.lower() == attrs["correo_electronico"]:
            raise serializers.ValidationError(
                {"palabra_secreta": ["Debe ser distinta de la contraseña y el correo."]}
            )
        candidate = Usuario(
            correo_electronico=attrs["correo_electronico"],
            nombre_completo=attrs["nombre_completo"],
        )
        try:
            validate_password(password, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"contrasena": exc.messages}) from exc
        return attrs


class RegistroUsuarioSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    nombre_completo = serializers.CharField(read_only=True)
    correo_electronico = serializers.EmailField(read_only=True)
    esta_activo = serializers.BooleanField(source="is_active", read_only=True)
    fecha_creacion = serializers.DateTimeField(source="date_joined", read_only=True)


class RegistroSuccessSerializer(serializers.Serializer):
    data = RegistroUsuarioSerializer()


class LoginInputSerializer(serializers.Serializer):
    correo = serializers.EmailField(max_length=255)
    contrasena = serializers.CharField(trim_whitespace=False, write_only=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Se requiere un objeto JSON."]}
            )
        extra = sorted(set(data) - set(self.fields))
        if extra:
            raise serializers.ValidationError(
                {name: ["Este campo no está permitido."] for name in extra}
            )
        invalid = {
            name: ["Debe ser una cadena de texto."]
            for name in self.fields
            if name in data and not isinstance(data[name], str)
        }
        if invalid:
            raise serializers.ValidationError(invalid)
        return super().to_internal_value(data)

    def validate_correo(self, value):
        return value.strip().lower()


class LoginTokensSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class LoginDataSerializer(serializers.Serializer):
    usuario = RegistroUsuarioSerializer(read_only=True)
    tokens = LoginTokensSerializer(read_only=True)


class LoginSuccessSerializer(serializers.Serializer):
    data = LoginDataSerializer(read_only=True)


class RecuperarContrasenaInputSerializer(serializers.Serializer):
    correo = serializers.EmailField(max_length=255)
    palabra_secreta = serializers.CharField(
        max_length=128, trim_whitespace=False, write_only=True
    )
    nueva_contrasena = serializers.CharField(
        min_length=8, max_length=128, trim_whitespace=False, write_only=True
    )
    confirmar_contrasena = serializers.CharField(
        min_length=8, max_length=128, trim_whitespace=False, write_only=True
    )

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Se requiere un objeto JSON."]}
            )
        extra = sorted(set(data) - set(self.fields))
        if extra:
            raise serializers.ValidationError(
                {name: ["Este campo no está permitido."] for name in extra}
            )
        invalid = {
            name: ["Debe ser una cadena de texto."]
            for name in self.fields
            if name in data and not isinstance(data[name], str)
        }
        if invalid:
            raise serializers.ValidationError(invalid)
        return super().to_internal_value(data)

    def validate_correo(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        password = attrs["nueva_contrasena"]
        confirmation = attrs["confirmar_contrasena"]
        secret = attrs["palabra_secreta"]
        if password != confirmation:
            raise serializers.ValidationError(
                {"confirmar_contrasena": ["Las contraseñas no coinciden."]}
            )
        if not password.strip():
            raise serializers.ValidationError(
                {"nueva_contrasena": ["No puede contener únicamente espacios."]}
            )
        if not secret.strip():
            raise serializers.ValidationError(
                {"palabra_secreta": ["No puede contener únicamente espacios."]}
            )
        if password == secret or password.lower() == attrs["correo"]:
            raise serializers.ValidationError(
                {"nueva_contrasena": ["Debe ser distinta de la palabra secreta y el correo."]}
            )
        candidate = Usuario(correo_electronico=attrs["correo"])
        try:
            validate_password(password, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"nueva_contrasena": exc.messages}) from exc
        return attrs


class RecuperarContrasenaSuccessSerializer(serializers.Serializer):
    mensaje = serializers.CharField(read_only=True)


class RegistroErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()), required=False
    )


class RegistroErrorSerializer(serializers.Serializer):
    error = RegistroErrorBodySerializer()
