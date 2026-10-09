"""Mapeo ORM de las tablas de suscripciones del esquema real (database/schema_desplegado.sql).

Los modelos son ``managed = False`` y solo describen columnas y relaciones
existentes. No crean ni migran tablas; el DDL pertenece al SQL.
"""

import uuid

from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """Fila de ``planes``. El id entero es el identificador público estable."""

    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    limite_almacenamiento_bytes = models.BigIntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esta_activo = models.BooleanField(default=True)

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
    estado = models.CharField(max_length=50, choices=ESTADOS, default=ESTADO_ACTIVE)
    intervalo = models.CharField(max_length=20, choices=INTERVALOS, default=INTERVALO_MENSUAL)
    periodo_inicio = models.DateTimeField()
    periodo_fin = models.DateTimeField()
    auto_renovar = models.BooleanField(default=True)

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
    fecha_creacion = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "organizaciones"

    def __str__(self):
        return self.nombre


class MiembroOrganizacion(models.Model):
    """Fila de ``miembros_organizacion``."""

    id = models.BigAutoField(primary_key=True)
    organizacion_id = models.UUIDField()
    usuario_id = models.UUIDField()
    nivel_rol = models.SmallIntegerField()
    fecha_union = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "miembros_organizacion"

    def __str__(self):
        return f"{self.usuario_id} -> {self.organizacion_id} ({self.nivel_rol})"


class HistorialPago(models.Model):
    """Fila de ``historial_pagos``; pagos simulados de suscripciones."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suscripcion = models.ForeignKey(
        Suscripcion, on_delete=models.CASCADE, db_column="suscripcion_id"
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=50)
    referencia_transaccion = models.CharField(max_length=255)
    fecha_pago = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "historial_pagos"

    def __str__(self):
        return f"{self.suscripcion_id} -> {self.estado}"
