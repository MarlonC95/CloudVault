from datetime import timedelta
from math import ceil

from django.utils import timezone
from rest_framework import serializers

from common.formatting import bytes_legibles

from .models import Archivo, Carpeta


class CarpetaSerializer(serializers.ModelSerializer):
    padre_id = serializers.SerializerMethodField()
    ruta_completa = serializers.SerializerMethodField()
    cantidad_archivos = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source="fecha_creacion", read_only=True)

    class Meta:
        model = Carpeta
        fields = ["id", "nombre", "cantidad_archivos", "padre_id", "ruta_completa", "organizacion_id", "creado_en"]
        read_only_fields = fields

    def get_padre_id(self, obj):
        padre = getattr(obj, "padre_visible", obj.padre_id)
        return str(padre) if padre is not None else None

    def get_ruta_completa(self, obj):
        if self.context.get("ocultar_ancestros"):
            return f"/{obj.nombre}"
        return obj.ruta_completa

    def get_cantidad_archivos(self, obj):
        total = 0
        pendientes = [obj]
        vistas = set()
        while pendientes:
            carpeta = pendientes.pop()
            if carpeta.pk in vistas:
                continue
            vistas.add(carpeta.pk)
            filtros = {"en_papelera": False, "organizacion_id": obj.organizacion_id}
            total += carpeta.archivos.filter(**filtros).count()
            pendientes.extend(carpeta.subcarpetas.filter(**filtros))
        return total


class ArchivoSerializer(serializers.ModelSerializer):
    tipo = serializers.SerializerMethodField()
    tamano_legible = serializers.SerializerMethodField()
    fecha_modificacion = serializers.DateTimeField(source="actualizado_en", read_only=True)
    propietario = serializers.SerializerMethodField()
    cifrado = serializers.SerializerMethodField()
    es_nuevo = serializers.SerializerMethodField()
    carpeta_id = serializers.SerializerMethodField()

    def get_carpeta_id(self, obj):
        carpeta = getattr(obj, "carpeta_visible", obj.carpeta_id)
        return str(carpeta) if carpeta is not None else None

    class Meta:
        model = Archivo
        fields = ["id", "nombre", "tipo", "tamano_bytes", "tamano_legible", "fecha_modificacion", "propietario", "cifrado", "es_nuevo", "en_papelera", "carpeta_id", "organizacion_id"]
        read_only_fields = fields

    def get_tipo(self, obj):
        return obj.nombre.rsplit(".", 1)[-1].lower() if "." in obj.nombre else "otro"

    def get_tamano_legible(self, obj):
        return bytes_legibles(obj.tamano_bytes)

    def get_propietario(self, obj):
        return {"id": str(obj.propietario_id), "nombre_completo": obj.propietario.nombre_completo}

    def get_cifrado(self, obj):
        return True

    def get_es_nuevo(self, obj):
        return obj.fecha_subida > timezone.now() - timedelta(hours=24)


class PapeleraSerializer(ArchivoSerializer):
    eliminado_en = serializers.DateTimeField(source="fecha_papelera", read_only=True)
    expira_en = serializers.SerializerMethodField()
    dias_restantes = serializers.SerializerMethodField()

    class Meta(ArchivoSerializer.Meta):
        fields = ["id", "nombre", "tipo", "tamano_legible", "eliminado_en", "expira_en", "dias_restantes", "carpeta_id"]

    def get_expira_en(self, obj):
        return obj.fecha_papelera + timedelta(days=30) if obj.fecha_papelera else None

    def get_dias_restantes(self, obj):
        expira = self.get_expira_en(obj)
        if not expira:
            return 0
        ahora = self.context.get("ahora_papelera")
        if ahora is None:
            ahora = timezone.now()
            self.context["ahora_papelera"] = ahora
        return max(0, ceil((expira - ahora).total_seconds() / 86400))
