"""Perfiles independientes; no lee archivos, contacta S3 ni imprime secretos."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class ConfiguracionS3Invalida(ValueError):
    pass


def _endpoint(valor, perfil):
    try:
        url = urlsplit(valor)
        puerto = url.port
        valido = (
            url.scheme in ({"https"} if perfil == "railway" else {"http", "https"})
            and url.hostname and not url.username and not url.password
            and url.path in ("", "/") and not url.query and not url.fragment
            and not any(c.isspace() for c in valor)
            and (puerto is None or 0 < puerto < 65536)
        )
    except (ValueError, TypeError):
        valido = False
    if not valido:
        raise ConfiguracionS3Invalida("Endpoint S3 inválido para el perfil elegido.")
    return valor.rstrip("/")


@dataclass(frozen=True)
class ConfiguracionS3:
    perfil: str
    endpoint: str
    region: str
    bucket: str
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    endpoint_firma: str | None = None
    estilo: str = "virtual"

    def __post_init__(self):
        if self.perfil not in {"railway", "minio"}:
            raise ConfiguracionS3Invalida("Perfil S3 desconocido.")
        object.__setattr__(self, "endpoint", _endpoint(self.endpoint, self.perfil))
        publico = _endpoint(self.endpoint_firma or self.endpoint, self.perfil)
        object.__setattr__(self, "endpoint_firma", publico)
        if self.perfil == "railway" and publico != self.endpoint:
            raise ConfiguracionS3Invalida("Railway requiere el mismo endpoint para acceso y firma.")
        if self.estilo not in {"virtual", "path"}:
            raise ConfiguracionS3Invalida("Estilo S3 inválido.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", self.bucket):
            raise ConfiguracionS3Invalida("Nombre de bucket inválido.")
        for nombre in ("region", "access_key", "secret_key"):
            valor = getattr(self, nombre)
            if not isinstance(valor, str) or not valor or any(c.isspace() for c in valor):
                raise ConfiguracionS3Invalida(f"Configuración S3 incompleta o inválida: {nombre}.")

    @classmethod
    def desde_entorno(cls, entorno=None, *, perfil=None):
        entorno = os.environ if entorno is None else entorno
        perfil = perfil or entorno.get("ALMACENAMIENTO_PERFIL", "railway")
        if perfil == "railway":
            nombres = ("AWS_ENDPOINT_URL", "AWS_REGION", "AWS_STORAGE_BUCKET_NAME",
                       "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
            publico = None
            estilo = entorno.get("AWS_S3_URL_STYLE", "virtual")
        elif perfil == "minio":
            nombres = ("S3_ENDPOINT_URL", "S3_REGION", "S3_BUCKET",
                       "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
            publico = entorno.get("S3_PUBLIC_ENDPOINT_URL")
            estilo = entorno.get("S3_URL_STYLE", "path")
        else:
            raise ConfiguracionS3Invalida("Perfil S3 desconocido.")
        # No hay fallback/aliases entre perfiles: S3_BUCKET no reemplaza AWS_*.
        faltantes = [nombre for nombre in nombres if not entorno.get(nombre)]
        if faltantes:
            raise ConfiguracionS3Invalida("Faltan variables S3: " + ", ".join(faltantes))
        return cls(perfil, *(entorno[nombre] for nombre in nombres),
                   endpoint_firma=publico, estilo=estilo)
