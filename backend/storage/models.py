import uuid

from django.conf import settings
from django.db import models


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    padre = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subcarpetas",
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default="#2563EB")
    color_fondo = models.CharField(max_length=7, default="#EFF6FF")
    ruta_completa = models.CharField(max_length=1024, default="/")
    en_papelera = models.BooleanField(default=False)
    fecha_papelera = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "padre", "nombre"],
                condition=models.Q(padre__isnull=False),
                name="unique_subfolder_name",
            ),
            models.UniqueConstraint(
                fields=["owner", "nombre"],
                condition=models.Q(padre__isnull=True),
                name="unique_root_folder_name",
            ),
        ]

    def __str__(self):
        return self.ruta_completa


class FileMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
    )
    carpeta = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        related_name="archivos",
        null=True,
        blank=True,
    )
    nombre_original = models.CharField(max_length=255)
    clave_s3 = models.CharField(max_length=1024, unique=True)
    tamano_bytes = models.PositiveBigIntegerField(default=0)
    tipo_mime = models.CharField(max_length=255, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    en_papelera = models.BooleanField(default=False)
    fecha_papelera = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre_original
