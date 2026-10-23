"""Ejecuta el hash fuera del proceso de la vista, con tamaño y tiempo acotados."""

import json
from pathlib import Path
import subprocess
import sys

from .s3 import ContenidoS3, ErrorS3, _clave
from .validacion import validar_checksum


class VerificadorSubproceso:
    def __init__(self, *, tiempo_maximo=60):
        if type(tiempo_maximo) is not int or not 1 <= tiempo_maximo <= 300:
            raise ValueError("Tiempo de verificación inválido")
        self.tiempo_maximo = tiempo_maximo

    def __call__(self, *, clave, tamano_bytes):
        _clave(clave, propia=True)
        if "/publicaciones/" not in clave or type(tamano_bytes) is not int or not 0 <= tamano_bytes <= 5 << 30:
            raise ValueError("Verificación inválida")
        try:
            resultado = subprocess.run(
                [sys.executable, "-m", "almacenamiento.verificar_publicacion"],
                cwd=Path(__file__).resolve().parents[1],
                input=json.dumps({"clave": clave, "tamano_bytes": tamano_bytes}),
                text=True, capture_output=True, timeout=self.tiempo_maximo, check=False)
            if len(resultado.stdout) > 1024:
                raise ErrorS3()
            datos = json.loads(resultado.stdout)
            if resultado.returncode != 0:
                raise ErrorS3("contenido" if datos == {"error": "contenido"} else "servicio")
            if not isinstance(datos, dict) or set(datos) != {"tamano_bytes", "sha256"}:
                raise ErrorS3()
            if type(datos["tamano_bytes"]) is not int or datos["tamano_bytes"] != tamano_bytes:
                raise ErrorS3("contenido")
            validar_checksum(datos["sha256"])
            if datos["sha256"] is None:
                raise ErrorS3()
            return ContenidoS3(datos["tamano_bytes"], datos["sha256"])
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError):
            raise ErrorS3() from None
