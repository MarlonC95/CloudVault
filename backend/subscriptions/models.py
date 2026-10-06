from django.conf import settings
from django.db import models


class Plan(models.Model):
    """Plan del catálogo (§10.1).

    ``slug`` es el id público del plan y actúa como clave primaria, por lo que
    el ``plan_id`` del contrato coincide con el valor expuesto en el catálogo.
    """

    slug = models.SlugField(max_length=50, primary_key=True)
    nombre = models.CharField(max_length=100)
    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # ``null`` representa almacenamiento ilimitado.
    almacenamiento_bytes = models.BigIntegerField(null=True, blank=True)
    es_popular = models.BooleanField(default=False)
    caracteristicas = models.JSONField(default=list, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["precio_mensual", "slug"]

    def __str__(self):
        return self.nombre


class Subscription(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CANCELADO = "cancelado", "Cancelado"

    class TipoFacturacion(models.TextChoices):
        MENSUAL = "mensual", "Mensual"
        ANUAL = "anual", "Anual"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suscripcion",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="suscripciones")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    tipo_facturacion = models.CharField(
        max_length=10,
        choices=TipoFacturacion.choices,
        default=TipoFacturacion.MENSUAL,
    )
    periodo_inicio = models.DateTimeField()
    periodo_fin = models.DateTimeField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.usuario_id} -> {self.plan_id}"
