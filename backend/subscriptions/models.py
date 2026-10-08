"""Mapeo ORM de las tablas de suscripciones propiedad del SQL compartido.

El esquema (``database/schema.sql``) es la fuente de verdad: los modelos son
``managed = False`` y solo describen columnas y relaciones. No crean ni migran
las tablas; la instalación pertenece al SQL.
"""

import uuid

from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """Fila de ``planes``. El id entero es el identificador público estable."""

    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    limite_almacenamiento_bytes = models.BigIntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esta_activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "planes"

    def __str__(self):
        return self.nombre


class Suscripcion(models.Model):
    """Fila de ``suscripciones``; una suscripción ACTIVE vigente por organización."""

    ESTADO_ACTIVE = "ACTIVE"
    ESTADO_PAST_DUE = "PAST_DUE"
    ESTADO_CANCELED = "CANCELED"
    INTERVALO_MENSUAL = "MONTHLY"
    INTERVALO_ANUAL = "YEARLY"

    ESTADOS = (
        (ESTADO_ACTIVE, "Activa"),
        (ESTADO_PAST_DUE, "Pago pendiente"),
        (ESTADO_CANCELED, "Cancelada"),
    )
    INTERVALOS = (
        (INTERVALO_MENSUAL, "Mensual"),
        (INTERVALO_ANUAL, "Anual"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizacion_id = models.UUIDField()
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_ACTIVE)
    intervalo = models.CharField(max_length=20, choices=INTERVALOS, default=INTERVALO_MENSUAL)
    periodo_inicio = models.DateTimeField()
    periodo_fin = models.DateTimeField()
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "suscripciones"

    def __str__(self):
        return f"{self.organizacion_id} -> {self.plan_id}"


class Organizacion(models.Model):
    """Solo el consumo necesario para cuotas; el CRUD pertenece a otro ámbito."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=150)
    slug = models.CharField(max_length=150, unique=True)
    almacenamiento_usado_bytes = models.BigIntegerField(default=0)
    esta_activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "organizaciones"

    def __str__(self):
        return self.nombre
