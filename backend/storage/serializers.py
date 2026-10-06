import os
from datetime import timedelta

from django.template.defaultfilters import filesizeformat
from django.utils import timezone
from rest_framework import serializers

from .models import FileMetadata, Folder


class FolderSerializer(serializers.ModelSerializer):
    padre_id = serializers.UUIDField(read_only=True)
    cantidad_archivos = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "nombre",
            "color",
            "color_fondo",
            "padre_id",
            "ruta_completa",
            "cantidad_archivos",
            "creado_en",
        ]
        read_only_fields = ["id", "padre_id", "ruta_completa", "cantidad_archivos", "creado_en"]

    def get_cantidad_archivos(self, obj):
        return obj.archivos.filter(en_papelera=False).count()


class PropietarioSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="pk", read_only=True)
    nombre_completo = serializers.CharField(read_only=True)


class FileMetadataSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="nombre_original", read_only=True)
    nombre_original = serializers.CharField(write_only=True, required=False)
    tipo = serializers.SerializerMethodField()
    tamano_legible = serializers.SerializerMethodField()
    fecha_modificacion = serializers.DateTimeField(source="actualizado_en", read_only=True)
    propietario = serializers.SerializerMethodField()
    cifrado = serializers.SerializerMethodField()
    es_nuevo = serializers.SerializerMethodField()
    carpeta_id = serializers.UUIDField(read_only=True)

    TIPOS_CONOCIDOS = {"pdf", "zip", "png", "js", "xlsx", "mp4", "docx"}

    class Meta:
        model = FileMetadata
        fields = [
            "id",
            "nombre",
            "nombre_original",
            "tipo",
            "tamano_bytes",
            "tamano_legible",
            "fecha_modificacion",
            "propietario",
            "cifrado",
            "es_nuevo",
            "en_papelera",
            "carpeta_id",
        ]

    def get_tipo(self, obj):
        ext = os.path.splitext(obj.nombre_original or "")[1].lower().lstrip(".")
        return ext if ext in self.TIPOS_CONOCIDOS else "otro"

    def get_tamano_legible(self, obj):
        return filesizeformat(obj.tamano_bytes)

    def get_propietario(self, obj):
        return PropietarioSerializer(obj.owner).data

    def get_cifrado(self, obj):
        return True

    def get_es_nuevo(self, obj):
        return (timezone.now() - obj.creado_en) < timedelta(hours=24)
