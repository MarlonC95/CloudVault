"""Mappings for tables maintained by database/schema.sql."""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, correo_electronico, password=None, **extra_fields):
        if not correo_electronico:
            raise ValueError("El correo electrónico es obligatorio")
        if not password:
            raise ValueError("La contraseña es obligatoria")
        correo = correo_electronico.strip().lower()
        user = self.model(correo_electronico=correo, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class Usuario(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    correo_electronico = models.EmailField(max_length=255, unique=True)
    password = models.CharField(max_length=255, db_column="contrasena_hash")
    nombre_completo = models.CharField(max_length=150)
    palabra_secreta_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_column="esta_activo")
    date_joined = models.DateTimeField(default=timezone.now, db_column="fecha_creacion")
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    is_2fa_enabled = models.BooleanField(default=False)
    last_login = None

    USERNAME_FIELD = "correo_electronico"
    EMAIL_FIELD = "correo_electronico"
    REQUIRED_FIELDS = ["nombre_completo"]

    objects = UsuarioManager()

    class Meta:
        managed = False
        db_table = "usuarios"

    def __str__(self):
        return self.correo_electronico


class LogAuditoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, db_column="usuario_id"
    )
    organizacion_id = models.UUIDField(null=True)
    accion = models.CharField(max_length=100)
    ip_origen = models.CharField(max_length=45, null=True)
    detalles = models.JSONField(null=True)
    fecha_evento = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "logs_auditoria"
