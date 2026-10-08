import os
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from auth_workspaces.models import Usuario
from common.formatting import bytes_legibles

from .models import Archivo, Carpeta


class PropietarioSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="pk", read_only=True)
    nombre_completo = serializers.CharField(read_only=True)


class CarpetaSerializer(serializers.ModelSerializer):
    carpeta_padre_id = serializers.UUIDField(source="padre_id", read_only=True)
    total_archivos = serializers.SerializerMethodField()
    total_tamano_bytes = serializers.SerializerMethodField()
    fecha_creacion = serializers.DateTimeField(source="creado_en", read_only=True)

    class Meta:
        model = Carpeta
        fields = [
            "id",
            "organizacion_id",
            "nombre",
            "carpeta_padre_id",
            "ruta_completa",
            "total_archivos",
            "total_tamano_bytes",
            "fecha_creacion",
        ]
        read_only_fields = [
            "id",
            "organizacion_id",
            "carpeta_padre_id",
            "ruta_completa",
            "total_archivos",
            "total_tamano_bytes",
            "fecha_creacion",
        ]

    def get_total_archivos(self, obj):
        total = 0
        stack = [obj]
        while stack:
            actual = stack.pop()
            total += actual.archivos.filter(en_papelera=False).count()
            stack.extend(actual.subcarpetas.filter(en_papelera=False))
        return total

    def get_total_tamano_bytes(self, obj):
        total = 0
        stack = [obj]
        while stack:
            actual = stack.pop()
            total += sum(
                actual.archivos.filter(en_papelera=False).values_list("tamano_bytes", flat=True)
            )
            stack.extend(actual.subcarpetas.filter(en_papelera=False))
        return total


class ArchivoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="nombre_original", read_only=True)
    nombre_original = serializers.CharField(write_only=True, required=False)
    fecha_creacion = serializers.DateTimeField(source="creado_en", read_only=True)
    fecha_modificacion = serializers.DateTimeField(source="actualizado_en", read_only=True)
    propietario = serializers.SerializerMethodField()
    carpeta_id = serializers.UUIDField(read_only=True)
    ruta_completa = serializers.SerializerMethodField()

    class Meta:
        model = Archivo
        fields = [
            "id",
            "organizacion_id",
            "carpeta_id",
            "nombre",
            "nombre_original",
            "tamano_bytes",
            "tipo_mime",
            "propietario",
            "fecha_creacion",
            "fecha_modificacion",
            "ruta_completa",
            "en_papelera",
        ]
        read_only_fields = [
            "id",
            "organizacion_id",
            "carpeta_id",
            "nombre",
            "tamano_bytes",
            "tipo_mime",
            "propietario",
            "fecha_creacion",
            "fecha_modificacion",
            "ruta_completa",
            "en_papelera",
        ]

    def get_propietario(self, obj):
        return PropietarioSerializer(obj.propietario).data

    def get_ruta_completa(self, obj):
        base = obj.carpeta.ruta_completa if obj.carpeta else ""
        return f"{base}/{obj.nombre_original}" if base else f"/{obj.nombre_original}"

    def update(self, instance, validated_data):
        nombre = validated_data.pop("nombre_original", None)
        if nombre is not None:
            instance.nombre_original = nombre
        return super().update(instance, validated_data)
