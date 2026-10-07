"""Contrato de Dani: inicio/confirmación implementados; descarga aún de diseño."""

import argparse
import json
from pathlib import Path

from .contrato import (
    CONFIRMAR_CARGA,
    DESCARGA,
    ESTADOS_HTTP_ERROR,
    ETAG_MAXIMO,
    INICIAR_CARGA,
    MIME_MAXIMO,
    MIME_PATRON,
    NOMBRE_MAXIMO,
    NOMBRE_PATRON,
    PoliticaCarga,
    UUID_PATRON,
)


def _objeto(properties, *, required=None):
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required is None:
        required = list(properties)
    if required:
        schema["required"] = required
    return schema


def _ref(nombre):
    return {"$ref": f"#/components/schemas/{nombre}"}


def _contenido(nombre):
    return {"application/json": {"schema": _ref(nombre)}}


def crear_openapi(*, politica=None):
    politica = politica or PoliticaCarga()
    uuid = {"type": "string", "format": "uuid", "pattern": UUID_PATRON}
    nombre = {
        "type": "string", "minLength": 1, "maxLength": NOMBRE_MAXIMO,
        "pattern": NOMBRE_PATRON,
    }
    mime = {
        "type": "string", "minLength": 1, "maxLength": MIME_MAXIMO,
        "pattern": MIME_PATRON,
    }
    fecha = {"type": "string", "format": "date-time", "description": "ISO 8601 en UTC."}
    url = {"type": "string", "format": "uri", "maxLength": 8192}
    schemas = {
        "IniciarCargaInput": _objeto({
            "nombre": nombre,
            "tamano_bytes": {
                "type": "integer", "format": "int64", "minimum": 0,
                "maximum": politica.maximo_archivo_bytes,
                "description": "Límite operativo del perfil documentado; la cuota se valida antes de firmar.",
            },
            "tipo_mime": mime,
            "carpeta_id": {**uuid, "nullable": True, "default": None},
        }, required=["nombre", "tamano_bytes", "tipo_mime"]),
        "ConfirmarCargaInput": _objeto({
            "etag": {
                "type": "string", "minLength": 1, "maxLength": ETAG_MAXIMO,
                "pattern": r"^[^\x00-\x1f\x7f]+$",
                "description": "Opcional; se conserva literalmente y no equivale a SHA-256.",
            },
        }, required=[]),
        "IniciarCargaSuccess": _objeto({"data": _objeto({
            "archivo_id": uuid,
            "url_subida": url,
            "metodo": {"type": "string", "enum": ["PUT"]},
            "encabezados": _objeto({"Content-Type": mime}),
            "expira_en": fecha,
        })}),
        "ConfirmarCargaSuccess": _objeto({"data": _objeto({
            "id": uuid,
            "nombre": nombre,
            "es_nuevo": {"type": "boolean"},
            "en_papelera": {"type": "boolean"},
        })}),
        "DescargaSuccess": _objeto({"data": _objeto({
            "url_descarga": url,
            "nombre": nombre,
            "expira_en": fecha,
        })}),
        "Error": _objeto({"error": _objeto({
            "code": {"type": "string", "enum": [codigo.value for codigo in ESTADOS_HTTP_ERROR]},
            "fields": {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            },
        }, required=["code"]) }),
    }
    paths = {}
    for operacion, entrada, salida in (
        (INICIAR_CARGA, "IniciarCargaInput", "IniciarCargaSuccess"),
        (CONFIRMAR_CARGA, "ConfirmarCargaInput", "ConfirmarCargaSuccess"),
        (DESCARGA, None, "DescargaSuccess"),
    ):
        errores = sorted(set(ESTADOS_HTTP_ERROR.values()))
        if operacion == DESCARGA:
            errores.remove(409)
        operation = {
            "operationId": operacion.nombre,
            "tags": ["Almacenamiento de Dani — diseño"],
            "x-estado-implementacion": ("endpoint-implementado-integracion-pendiente"
                                        if operacion in (INICIAR_CARGA, CONFIRMAR_CARGA)
                                        else "contrato-validado-endpoint-pendiente"),
            "security": [{"BearerAuth": []}],
            "responses": {
                str(operacion.estado_exito): {
                    "description": "Respuesta definida por el PDF vigente.",
                    "content": _contenido(salida),
                },
                **{
                    str(estado): {
                        "description": ", ".join(
                            codigo.value for codigo, http in ESTADOS_HTTP_ERROR.items()
                            if http == estado
                        ),
                        "content": _contenido("Error"),
                    } for estado in errores
                },
            },
        }
        if entrada:
            operation["requestBody"] = {
                "required": operacion == INICIAR_CARGA,
                "content": _contenido(entrada),
            }
        if "{id}" in operacion.ruta:
            operation["parameters"] = [{
                "name": "id", "in": "path", "required": True, "schema": uuid,
            }]
        paths[operacion.ruta] = {operacion.metodo.lower(): operation}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CloudVault — contrato de almacenamiento de Dani",
            "version": "fase-05",
            "description": (
                "Contrato de diseño basado en Contratos de API - CloudVault.pdf. "
                "Inicio y confirmación instalados y probados con servicios sintéticos; proveedor real pendiente. "
                "Descarga conserva su contrato de diseño, sin endpoint instalado."
            ),
        },
        "x-fuente": "agente/referencias/contrato-api-vigente.pdf, secciones 0, 4 y 5",
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(crear_openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
