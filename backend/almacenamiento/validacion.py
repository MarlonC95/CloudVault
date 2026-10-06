"""Validadores internos compartidos; no normalizan el JSON de la API."""

import re


def validar_texto_tecnico(valor, limite, campo):
    if not isinstance(valor, str) or not valor or len(valor) > limite or any(
        ord(c) < 32 or ord(c) == 127 for c in valor
    ):
        raise ValueError(f"{campo} inválido")
    return valor


def validar_checksum(valor):
    if valor is not None and (not isinstance(valor, str) or not re.fullmatch(r"[0-9a-f]{64}", valor)):
        raise ValueError("Checksum inválido")
    return valor
