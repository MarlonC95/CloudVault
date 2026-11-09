"""Proyección pública del listado; no serializa modelos de usuario completos."""

from datetime import timezone

from rest_framework import serializers


class MiembroOrganizacionSerializer(serializers.Serializer):
    usuario_id = serializers.UUIDField(read_only=True)
    nombre_completo = serializers.CharField(read_only=True)
    correo_electronico = serializers.EmailField(read_only=True)
    rol = serializers.CharField(read_only=True)
    nivel_rol = serializers.IntegerField(read_only=True)
    fecha_ingreso = serializers.DateTimeField(read_only=True, default_timezone=timezone.utc)
