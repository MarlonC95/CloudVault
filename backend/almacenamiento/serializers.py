"""Validación del JSON de Dani, independiente de modelos ajenos."""

import re

from rest_framework import serializers

from .contrato import (
    CodigoError,
    ETAG_MAXIMO,
    MIME_MAXIMO,
    MIME_PATRON,
    NOMBRE_MAXIMO,
    NOMBRE_PATRON,
    PoliticaCarga,
    TAMANO_SQL_MAXIMO,
    UUID_PATRON,
)


class SerializerEstricto(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"non_field_errors": ["Se requiere un objeto JSON."]}
            )
        extras = set(data) - set(self.fields)
        if extras:
            raise serializers.ValidationError(
                {str(campo): ["Este campo no está permitido."] for campo in sorted(extras)}
            )
        return super().to_internal_value(data)


class TextoEstricto(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class UUIDTexto(serializers.UUIDField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(UUID_PATRON, data):
            self.fail("invalid")
        return super().to_internal_value(data)


class BytesEnteros(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class BooleanoEstricto(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid")
        return super().to_internal_value(data)


class NombreArchivo(TextoEstricto):
    def __init__(self, **kwargs):
        super().__init__(max_length=NOMBRE_MAXIMO, trim_whitespace=True, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(NOMBRE_PATRON, value):
            raise serializers.ValidationError(
                "Debe ser un nombre de archivo sin rutas ni caracteres de control."
            )
        return value


class TipoMime(TextoEstricto):
    def __init__(self, **kwargs):
        super().__init__(max_length=MIME_MAXIMO, trim_whitespace=False, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(MIME_PATRON, value):
            raise serializers.ValidationError("Se requiere un MIME de tipo/subtipo.")
        return value


class IniciarCargaInputSerializer(SerializerEstricto):
    nombre = NombreArchivo()
    tamano_bytes = BytesEnteros(min_value=0, max_value=TAMANO_SQL_MAXIMO)
    tipo_mime = TipoMime()
    carpeta_id = UUIDTexto(required=False, allow_null=True, default=None)

    def validate_tamano_bytes(self, value):
        politica = self.context.get("politica", PoliticaCarga())
        if value > politica.maximo_archivo_bytes:
            raise serializers.ValidationError("El archivo supera el límite operativo permitido.")
        return value


class ConfirmarCargaInputSerializer(SerializerEstricto):
    etag = TextoEstricto(
        required=False, max_length=ETAG_MAXIMO, trim_whitespace=False
    )

    def validate_etag(self, value):
        if any(ord(caracter) < 32 or ord(caracter) == 127 for caracter in value):
            raise serializers.ValidationError("El ETag no admite caracteres de control.")
        return value


class ArchivoIdSerializer(SerializerEstricto):
    id = UUIDTexto()


class EncabezadosSubidaSerializer(SerializerEstricto):
    def get_fields(self):
        return {
            "Content-Type": TipoMime()
        }


class IniciarCargaDataSerializer(SerializerEstricto):
    archivo_id = UUIDTexto()
    url_subida = serializers.URLField(max_length=8192)
    metodo = serializers.ChoiceField(choices=["PUT"])
    encabezados = EncabezadosSubidaSerializer()
    expira_en = serializers.DateTimeField()


class IniciarCargaSuccessSerializer(SerializerEstricto):
    data = IniciarCargaDataSerializer()


class ConfirmarCargaDataSerializer(SerializerEstricto):
    id = UUIDTexto()
    nombre = NombreArchivo()
    es_nuevo = BooleanoEstricto()
    en_papelera = BooleanoEstricto()


class ConfirmarCargaSuccessSerializer(SerializerEstricto):
    data = ConfirmarCargaDataSerializer()


class DescargaDataSerializer(SerializerEstricto):
    url_descarga = serializers.URLField(max_length=8192)
    nombre = NombreArchivo()
    expira_en = serializers.DateTimeField()


class DescargaSuccessSerializer(SerializerEstricto):
    data = DescargaDataSerializer()


class ErrorBodySerializer(SerializerEstricto):
    code = serializers.ChoiceField(choices=[codigo.value for codigo in CodigoError])
    fields = serializers.DictField(
        child=serializers.ListField(child=TextoEstricto()), required=False
    )


class ErrorSerializer(SerializerEstricto):
    error = ErrorBodySerializer()
