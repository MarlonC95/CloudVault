"""Enlaces y permisos por usuario sobre archivos/carpetas (``database/compartir.sql``)."""

import uuid

from django.db import models
from django.utils import timezone

from auth_workspaces.models import Usuario
from storage.models import Archivo, Carpeta

LECTURA, ESCRITURA = "LECTURA", "ESCRITURA"
ROLES = ((LECTURA, LECTURA), (ESCRITURA, ESCRITURA))


class EnlacePublico(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=255, unique=True, db_column="token_random")
    archivo = models.ForeignKey(Archivo, null=True, on_delete=models.CASCADE, related_name="+")
    carpeta = models.ForeignKey(Carpeta, null=True, on_delete=models.CASCADE, related_name="+")
    contrasena_hash = models.CharField(max_length=255, null=True)
    fecha_expiracion = models.DateTimeField(null=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    creado_por = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="+")
    rol = models.CharField(max_length=20, choices=ROLES, default=LECTURA)
    permite_descarga = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "enlaces_publicos"

    @property
    def recurso(self):
        return self.archivo or self.carpeta


class PermisoRecurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    archivo = models.ForeignKey(Archivo, null=True, on_delete=models.CASCADE, related_name="+")
    carpeta = models.ForeignKey(Carpeta, null=True, on_delete=models.CASCADE, related_name="+")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="+")
    tipo_permiso = models.CharField(max_length=50, choices=ROLES)
    permite_descarga = models.BooleanField(default=True)
    enlace = models.ForeignKey(EnlacePublico, null=True, on_delete=models.CASCADE, related_name="+")
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "permisos_recurso"
