"""Mapping de las dos tablas técnicas. Su instalación pertenece al SQL compartido.

Las referencias externas son UUID: PostgreSQL conserva sus FK reales, sin
duplicar los modelos de usuarios, organizaciones, carpetas o archivos.
"""

from django.db import models
from django.db.models.functions import Now

from .contrato import CLAVE_LEDGER_SQL_MAXIMA, CLAVE_TEMPORAL_SQL_MAXIMA


class EstadoSesion(models.TextChoices):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class EstadoPublicacion(models.TextChoices):
    PREPARED = "PREPARED"
    PUBLISHED = "PUBLISHED"
    ABANDONED = "ABANDONED"
    CLEANED = "CLEANED"


class SesionCarga(models.Model):
    id = models.UUIDField(primary_key=True, db_default=models.Func(function="gen_random_uuid"))
    archivo_id = models.UUIDField(unique=True)
    solicitante_id = models.UUIDField()
    organizacion_id = models.UUIDField()
    carpeta_id = models.UUIDField(null=True)
    nombre = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=100)
    tamano_bytes = models.BigIntegerField()
    checksum_sha256 = models.CharField(max_length=64, null=True)
    etag = models.CharField(max_length=255, null=True)
    clave_temporal = models.CharField(max_length=CLAVE_TEMPORAL_SQL_MAXIMA, unique=True)
    expira_en = models.DateTimeField()
    estado = models.CharField(max_length=10, choices=EstadoSesion.choices, db_default="PENDING")
    resultado_confirmacion = models.JSONField(null=True)
    creado_en = models.DateTimeField(db_default=Now())
    actualizado_en = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "sesiones_carga"


class IntentoPublicacion(models.Model):
    id = models.UUIDField(primary_key=True, db_default=models.Func(function="gen_random_uuid"))
    sesion = models.OneToOneField(SesionCarga, on_delete=models.PROTECT, db_column="sesion_id")
    clave_final = models.CharField(max_length=CLAVE_LEDGER_SQL_MAXIMA, unique=True)
    etag_origen = models.CharField(max_length=255)
    version_origen = models.CharField(max_length=255, null=True)
    checksum_origen = models.CharField(max_length=64, null=True)
    etag_final = models.CharField(max_length=255, null=True)
    version_final = models.CharField(max_length=255, null=True)
    estado = models.CharField(max_length=10, choices=EstadoPublicacion.choices, db_default="PREPARED")
    creado_en = models.DateTimeField(db_default=Now())
    actualizado_en = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "intentos_publicacion"
