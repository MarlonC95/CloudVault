"""Cliente técnico de Dani. El coordinador autoriza/reserva antes de firmar.

No accede a SQL, no monta vistas y no sustituye permisos de German.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .configuracion_s3 import ConfiguracionS3
from .contrato import CodigoError, PoliticaCarga, MIME_PATRON
from .errores import ErrorCarga
from .validacion import validar_texto_tecnico


PREFIJO_PROPIO = "cloudvault/dani/"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_TECNICA = re.compile(rf"cloudvault/dani/(?:(?:temporales|publicaciones)/{_UUID}|pruebas/{_UUID}/{_UUID})\Z")


class ErrorS3(ErrorCarga):
    def __init__(self, tipo="servicio"):
        self.tipo = tipo
        super().__init__(CodigoError.NO_ENCONTRADO if tipo == "ausente"
                         else CodigoError.SERVICE_UNAVAILABLE)


@dataclass(frozen=True)
class FirmaS3:
    url: str = field(repr=False)
    metodo: str
    encabezados: dict
    expira_en: datetime


@dataclass(frozen=True)
class ObjetoS3:
    tamano_bytes: int
    tipo_mime: str
    etag: str
    version: str | None = None
    checksum_sha256: str | None = None  # Base64 del proveedor; no es hex ni ETag.


@dataclass(frozen=True)
class ContenidoS3:
    tamano_bytes: int
    sha256: str


def nueva_clave_temporal():
    return f"{PREFIJO_PROPIO}temporales/{uuid4()}"


def nueva_clave_final(archivo_id):
    return f"{PREFIJO_PROPIO}publicaciones/{UUID(str(archivo_id))}"


def _clave(clave, *, propia=False):
    validar_texto_tecnico(clave, 255, "clave S3")
    if clave.startswith("/") or "\\" in clave or any(p in {"", ".", ".."} for p in clave.split("/")):
        raise ValueError("Clave S3 inválida.")
    if propia and not _TECNICA.fullmatch(clave):
        raise ValueError("La operación requiere una clave técnica propia.")
    return clave


class ClienteS3:
    def __init__(self, configuracion: ConfiguracionS3, *, politica=None):
        self.configuracion = configuracion
        self.politica = politica or PoliticaCarga()
        config = Config(
            signature_version="s3v4", connect_timeout=5, read_timeout=15,
            retries={"mode": "standard", "total_max_attempts": 3},
            s3={"addressing_style": configuracion.estilo},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        )
        # Credenciales explícitas: no usa perfiles AWS locales ni metadata IAM.
        session = boto3.session.Session()
        opciones = dict(region_name=configuracion.region,
                        aws_access_key_id=configuracion.access_key,
                        aws_secret_access_key=configuracion.secret_key,
                        config=config, verify=True)
        self._cliente = session.client("s3", endpoint_url=configuracion.endpoint, **opciones)
        self._firmador = (self._cliente if configuracion.endpoint_firma == configuracion.endpoint
                         else session.client("s3", endpoint_url=configuracion.endpoint_firma, **opciones))

    def cerrar(self):
        self._cliente.close()
        if self._firmador is not self._cliente:
            self._firmador.close()

    def _operar(self, metodo, **parametros):
        try:
            return getattr(self._cliente, metodo)(Bucket=self.configuracion.bucket, **parametros)
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code", "")
            tipo = ("ausente" if codigo in {"404", "NoSuchKey", "NotFound"}
                    else "precondicion" if codigo in {"412", "PreconditionFailed"}
                    else "acceso" if codigo in {"403", "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}
                    else "servicio")
            raise ErrorS3(tipo) from None
        except BotoCoreError:
            raise ErrorS3() from None

    def _firmar(self, operacion, clave, vigencia, maximo, *, mime=None):
        _clave(clave, propia=operacion == "put_object")
        if operacion == "put_object" and "/publicaciones/" in clave:
            raise ValueError("No se firma PUT sobre una publicación.")
        if type(vigencia) is not int or not 0 < vigencia <= maximo:
            raise ValueError("Vigencia de firma inválida.")
        parametros = {"Bucket": self.configuracion.bucket, "Key": clave}
        headers = {}
        if mime is not None:
            if not isinstance(mime, str) or len(mime) > 100 or not re.fullmatch(MIME_PATRON, mime):
                raise ValueError("MIME inválido.")
            parametros["ContentType"] = mime
            headers["Content-Type"] = mime
        metodo = "PUT" if operacion == "put_object" else "GET"
        try:
            url = self._firmador.generate_presigned_url(
                operacion, Params=parametros, ExpiresIn=vigencia, HttpMethod=metodo)
        except (BotoCoreError, ClientError):
            raise ErrorS3() from None
        return FirmaS3(url, metodo, headers, datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=vigencia))

    def firmar_put(self, clave, tipo_mime, *, vigencia=None):
        return self._firmar("put_object", clave,
                            self.politica.vigencia_carga_segundos if vigencia is None else vigencia,
                            self.politica.vigencia_carga_segundos, mime=tipo_mime)

    def firmar_get(self, clave, *, vigencia=None):
        return self._firmar("get_object", clave,
                            self.politica.vigencia_descarga_segundos if vigencia is None else vigencia,
                            self.politica.vigencia_descarga_segundos)

    def consultar(self, clave):
        respuesta = self._operar("head_object", Key=_clave(clave))
        tamano, etag = respuesta.get("ContentLength"), respuesta.get("ETag")
        if type(tamano) is not int or tamano < 0 or not isinstance(etag, str) or not etag:
            raise ErrorS3()
        return ObjetoS3(tamano, respuesta.get("ContentType", "application/octet-stream"), etag,
                        respuesta.get("VersionId"), respuesta.get("ChecksumSHA256"))

    def verificar_contenido(self, clave, *, maximo_bytes):
        """Lee por bloques para calcular hash real, sin fiarse de MIME/ETag/HEAD.

        Es una primitiva interna para verificación, nunca una vista de subida.
        """
        if type(maximo_bytes) is not int or not 0 <= maximo_bytes <= self.politica.maximo_archivo_bytes:
            raise ValueError("Límite de lectura inválido.")
        respuesta = self._operar("get_object", Key=_clave(clave))
        stream = respuesta["Body"]
        total, sha = 0, hashlib.sha256()
        try:
            while True:
                bloque = stream.read(min(65536, maximo_bytes - total + 1))
                if not bloque:
                    break
                total += len(bloque)
                if total > maximo_bytes:
                    raise ErrorS3("contenido")
                sha.update(bloque)
        except (BotoCoreError, OSError):
            raise ErrorS3() from None
        finally:
            stream.close()
        return ContenidoS3(total, sha.hexdigest())

    def copiar(self, origen, destino, *, etag_origen):
        _clave(origen, propia=True)
        _clave(destino, propia=True)
        if origen == destino or not ("/publicaciones/" in destino or "/pruebas/" in destino):
            raise ValueError("Destino técnico inválido para publicación.")
        validar_texto_tecnico(etag_origen, 255, "ETag")
        respuesta = self._operar("copy_object", Key=destino,
                                  CopySource={"Bucket": self.configuracion.bucket, "Key": origen},
                                  CopySourceIfMatch=etag_origen)
        # HTTP 200 no basta: SDK procesa el XML y aquí exigimos resultado.
        if not respuesta.get("CopyObjectResult", {}).get("ETag"):
            raise ErrorS3()
        # No presupone que el proveedor respete la condición: fase 05 debe
        # verificar contenido/recuperación antes de publicar metadatos.
        return self.consultar(destino)

    def borrar_tecnico(self, clave):
        """El coordinador debe probar que no sea una publicación vigente."""
        try:
            self._operar("delete_object", Key=_clave(clave, propia=True))
        except ErrorS3 as exc:
            if exc.tipo != "ausente":
                raise
