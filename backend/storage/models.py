import uuid

from django.db import models

from auth_workspaces.models import Usuario


class Carpeta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacion_id = models.UUIDField(null=True, blank=True, db_column="organizacion_id")
    padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column="carpeta_padre_id",
        related_name="subcarpetas",
    )
    propietario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="propietario_id",
        related_name="carpetas",
    )
    nombre = models.CharField(max_length=255)
    ruta_completa = models.TextField(default="/")
    en_papelera = models.BooleanField(default=False)
    fecha_papelera = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "carpetas"


class Archivo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacion_id = models.UUIDField(null=True, blank=True, db_column="organizacion_id")
    carpeta = models.ForeignKey(
        Carpeta,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="carpeta_id",
        related_name="archivos",
    )
    propietario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column="propietario_id",
        related_name="archivos",
    )
    nombre_original = models.CharField(max_length=255)
    clave_s3 = models.CharField(max_length=255, unique=True)
    tamano_bytes = models.BigIntegerField(default=0)
    tipo_mime = models.CharField(max_length=100)
    checksum_sha256 = models.CharField(max_length=64, null=True, blank=True)
    en_papelera = models.BooleanField(default=False)
    fecha_papelera = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "archivos"
