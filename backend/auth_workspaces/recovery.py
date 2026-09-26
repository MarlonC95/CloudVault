"""Atomic password recovery using the separately hashed secret phrase."""

import ipaddress

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import LogAuditoria, Usuario


class DatosRecuperacionInvalidos(APIException):
    status_code = 401
    default_detail = "No fue posible verificar los datos proporcionados"
    default_code = "RECOVERY_VERIFICATION_FAILED"


_DUMMY_SECRET_HASH = make_password("frase ficticia solo para comprobación")


def recuperar_contrasena(datos, remote_addr=None):
    correo = datos["correo"]
    ip = None
    if remote_addr:
        try:
            ip = str(ipaddress.ip_address(remote_addr))
        except ValueError:
            pass

    with transaction.atomic():
        # The API persists normalized email. The exact lookup uses its unique
        # index; the fallback preserves access to older mixed-case rows.
        usuarios = Usuario.objects.select_for_update()
        usuario = usuarios.filter(correo_electronico=correo).first()
        if usuario is None:
            usuario = usuarios.filter(correo_electronico__iexact=correo).first()

        hash_guardado = usuario.palabra_secreta_hash if usuario else _DUMMY_SECRET_HASH
        if not check_password(datos["palabra_secreta"], hash_guardado) or usuario is None:
            raise DatosRecuperacionInvalidos()

        try:
            validate_password(datos["nueva_contrasena"], user=usuario)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"nueva_contrasena": exc.messages}) from exc

        usuario.password = make_password(datos["nueva_contrasena"])
        usuario.save(update_fields=["password"])
        LogAuditoria.objects.create(
            usuario=usuario,
            accion="PASSWORD_RECOVERED",
            ip_origen=ip,
            detalles={},
        )
