"""Contrato de Dani: tres rutas implementadas con integración real pendiente."""

import argparse
import json
from copy import deepcopy
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


ESTADOS_POR_OPERACION = {
    INICIAR_CARGA.nombre: (400, 401, 403, 404, 405, 409, 429, 500, 503),
    CONFIRMAR_CARGA.nombre: (400, 401, 403, 404, 405, 409, 500, 503),
    DESCARGA.nombre: (400, 401, 403, 404, 405, 429, 500, 503),
}


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
        }) }),
    }
    paths = {}
    for operacion, entrada, salida in (
        (INICIAR_CARGA, "IniciarCargaInput", "IniciarCargaSuccess"),
        (CONFIRMAR_CARGA, "ConfirmarCargaInput", "ConfirmarCargaSuccess"),
        (DESCARGA, None, "DescargaSuccess"),
    ):
        errores = ESTADOS_POR_OPERACION[operacion.nombre]
        operation = {
            "operationId": operacion.nombre,
            "tags": ["Almacenamiento"],
            "x-estado-implementacion": "endpoint-implementado-integracion-pendiente",
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
                            if http == (400 if estado == 405 else estado)
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
        for estado, respuesta in operation["responses"].items():
            respuesta["headers"] = {
                "Cache-Control": {"schema": {"type": "string", "enum": ["no-store"]}},
                "Referrer-Policy": {"schema": {"type": "string", "enum": ["no-referrer"]}},
            }
            if estado == "401":
                respuesta["headers"]["WWW-Authenticate"] = {
                    "schema": {"type": "string", "enum": ["Bearer"]}}
            if estado == "429":
                respuesta["headers"]["Retry-After"] = {
                    "description": "Segundos hasta reintentar cuando el limitador los conoce.",
                    "schema": {"type": "string", "pattern": "^[0-9]+$"}}
        paths[operacion.ruta] = {operacion.metodo.lower(): operation}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CloudVault — contrato de almacenamiento de Dani",
            "version": "fase-09",
            "description": (
                "Contrato ejecutable basado en Contratos de API - CloudVault.pdf. "
                "Inicio, confirmación y descarga instalados y probados con servicios sintéticos; "
                "mantenimiento interno y periódico propio disponible. "
                "Proveedor real, SQL compartido y ejecución periódica en el ambiente compartido pendientes."
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


def expandir_schema(schema, documento):
    """Fragmentos autónomos para Swagger; no reemplaza esquemas de otros módulos."""
    if isinstance(schema, list):
        return [expandir_schema(item, documento) for item in schema]
    if not isinstance(schema, dict):
        return deepcopy(schema)
    if "$ref" in schema:
        objetivo = documento
        for segmento in schema["$ref"].removeprefix("#/").split("/"):
            objetivo = objetivo[segmento]
        return expandir_schema(objetivo, documento)
    return {clave: expandir_schema(valor, documento) for clave, valor in schema.items()}


def documentacion_operacion(operacion):
    """Decoración propia de drf-spectacular desde el mismo contrato exportable."""
    from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

    documento = crear_openapi()
    datos = documento["paths"][operacion.ruta][operacion.metodo.lower()]
    respuestas = {
        int(estado): OpenApiResponse(
            response=expandir_schema(respuesta["content"]["application/json"]["schema"], documento),
            description=respuesta["description"],
        ) for estado, respuesta in datos["responses"].items()
    }
    parametros = [OpenApiParameter(
        nombre, type=definicion["schema"], location=OpenApiParameter.HEADER,
        response=[int(estado)], description=definicion.get("description", ""),
    ) for estado, respuesta in datos["responses"].items()
        for nombre, definicion in respuesta["headers"].items()]
    # Un solo parámetro de header por nombre, con todos sus status asociados.
    headers = {}
    for parametro in parametros:
        if parametro.name in headers:
            headers[parametro.name].response.extend(parametro.response)
        else:
            headers[parametro.name] = parametro
    parametros = list(headers.values())
    for parametro in datos.get("parameters", []):
        parametros.append(OpenApiParameter(parametro["name"], type=parametro["schema"],
                                           location=OpenApiParameter.PATH, required=True))
    entrada = datos.get("requestBody")
    return {
        "operation_id": operacion.nombre, "tags": datos["tags"],
        "request": ({"application/json": expandir_schema(
            entrada["content"]["application/json"]["schema"], documento)} if entrada else None),
        "responses": respuestas, "parameters": parametros,
        "extensions": {"x-estado-implementacion": datos["x-estado-implementacion"]},
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
