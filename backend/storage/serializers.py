from rest_framework import serializers

from .models import FileMetadata, Folder


class FolderSerializer(serializers.ModelSerializer):
    padre_id = serializers.UUIDField(read_only=True)
    cantidad_archivos = serializers.IntegerField(source="archivos.count", read_only=True)

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


class FileMetadataSerializer(serializers.ModelSerializer):
    carpeta_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = FileMetadata
        fields = [
            "id",
            "nombre_original",
            "tamano_bytes",
            "tipo_mime",
            "carpeta_id",
            "creado_en",
        ]
