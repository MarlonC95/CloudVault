"""Contratos preparatorios de F3, sin consultas, permisos ni escrituras.

Validar un cambio no autoriza ni deshabilita cuentas. El privilegio global y la
revocación durable siguen sin soporte. Estos serializers no están en una ruta.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
from uuid import UUID

from django.utils.timezone import is_naive
from rest_framework import serializers


class EstadoCuentaInputSerializer(serializers.Serializer):
    esta_activo = serializers.BooleanField()
    motivo = serializers.CharField(min_length=1, max_length=500, trim_whitespace=True, write_only=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or any(not isinstance(k, str) for k in data):
            raise serializers.ValidationError({"non_field_errors": ["Se requiere un objeto JSON."]})
        extra = sorted(set(data) - set(self.fields))
        if extra:
            raise serializers.ValidationError({
                nombre: ["Este campo no está permitido."] for nombre in extra
            })
        # El PATCH contractual exige ambos campos incluso si un llamador usa
        # partial=True; no delegar esa obligatoriedad al modo parcial de DRF.
        errores = {
            nombre: ["Este campo es obligatorio."]
            for nombre in self.fields if nombre not in data
        }
        if "esta_activo" in data and type(data["esta_activo"]) is not bool:
            errores["esta_activo"] = ["Debe ser un booleano JSON."]
        if "motivo" in data and not isinstance(data["motivo"], str):
            errores["motivo"] = ["Debe ser una cadena de texto."]
        if errores:
            raise serializers.ValidationError(errores)
        return super().to_internal_value(data)


class UsuarioAdministrativoSerializer(serializers.Serializer):
    """Proyecta una fila completa; no calcula ni inventa sus agregados.

    El repositorio futuro debe calcular organizaciones distintas y bytes de
    archivos por propietario, incluidos los de papelera, sin multiplicar por
    membresías. Aquí ambos totales son obligatorios y no se consultan modelos.
    """

    id = serializers.UUIDField()
    nombre_completo = serializers.CharField(max_length=150, trim_whitespace=False)
    correo_electronico = serializers.EmailField(max_length=255, trim_whitespace=False)
    esta_activo = serializers.BooleanField()
    organizaciones_count = serializers.IntegerField(min_value=0)
    almacenamiento_propietario_bytes = serializers.IntegerField(min_value=0)
    fecha_registro = serializers.DateTimeField(default_timezone=timezone.utc)

    def get_initial(self):
        # DRF usa get_initial en .data si no hay instancia: no fabricar una fila
        # vacía ni totales implícitos en ese caso.
        raise serializers.ValidationError({"non_field_errors": ["Se requiere una fila completa."]})

    def to_internal_value(self, instance):
        if not isinstance(instance, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Se requiere una fila completa."]})
        errores = {
            nombre: ["Este dato es obligatorio."]
            for nombre in self.fields if nombre not in instance
        }
        if "id" in instance and not isinstance(instance["id"], (UUID, str)):
            errores["id"] = ["Debe ser un UUID."]
        for nombre in ("organizaciones_count", "almacenamiento_propietario_bytes"):
            if nombre in instance and type(instance[nombre]) is not int:
                errores[nombre] = ["Debe ser un entero no negativo calculado por el repositorio."]
        if "esta_activo" in instance and type(instance["esta_activo"]) is not bool:
            errores["esta_activo"] = ["Debe ser un booleano."]
        for nombre in ("nombre_completo", "correo_electronico"):
            if nombre in instance and not isinstance(instance[nombre], str):
                errores[nombre] = ["Debe ser una cadena de texto."]
        if "fecha_registro" in instance:
            fecha = instance["fecha_registro"]
            if not isinstance(fecha, datetime) or is_naive(fecha):
                errores["fecha_registro"] = ["Debe ser una fecha con zona horaria."]
        if errores:
            raise serializers.ValidationError(errores)
        return super().to_internal_value(instance)

    def to_representation(self, instance):
        # Valida los campos obligatorios y proyecta solo los declarados, aunque
        # la fila recibida contenga datos privados o atributos privilegiados.
        validado = self.to_internal_value(instance)
        return super().to_representation(validado)
