"""Permiso específico de envío; no altera los roles globales ni crea grants."""

from rest_framework.exceptions import NotFound, PermissionDenied

LECTURA = {"LECTURA", "read", "ESCRITURA", "write", "ADMINISTRACION", "admin"}
EDICION = {"ESCRITURA", "write", "ADMINISTRACION", "admin"}


def autorizar_envio(nivel, permisos):
    if nivel == 0:
        return
    if nivel != 3:
        raise PermissionDenied()
    validos = {p for p in permisos if isinstance(p, str)}
    if not validos & LECTURA:
        raise NotFound()
    if not validos & EDICION:
        raise PermissionDenied()
