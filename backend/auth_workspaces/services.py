"""Transactional registration operations."""

import ipaddress

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException

from .models import LogAuditoria, Usuario


class CorreoEnUso(APIException):
    status_code = 409
    default_detail = "No se pudo completar el registro con ese correo."
    default_code = "CORREO_EN_USO"


def registrar_usuario(datos, remote_addr=None):
    correo = datos["correo_electronico"]
    if Usuario.objects.filter(correo_electronico__iexact=correo).exists():
        raise CorreoEnUso()

    ip = None
    if remote_addr:
        try:
            ip = str(ipaddress.ip_address(remote_addr))
        except ValueError:
            pass

    try:
        with transaction.atomic():
            usuario = Usuario(
                correo_electronico=correo,
                nombre_completo=datos["nombre_completo"],
            )
            usuario.set_password(datos["contrasena"])
            usuario.palabra_secreta_hash = make_password(datos["palabra_secreta"])
            usuario.save(force_insert=True)
            LogAuditoria.objects.create(
                usuario=usuario,
                accion="USER_REGISTERED",
                ip_origen=ip,
                detalles={},
            )
    except IntegrityError as exc:
        cause = getattr(exc, "__cause__", None)
        constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
        if constraint == "usuarios_correo_electronico_key":
            raise CorreoEnUso() from exc
        raise
    return usuario
