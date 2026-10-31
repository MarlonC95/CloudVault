"""Filtros y proyección pública de auditoría; sin acceso a modelos o servicios."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from uuid import UUID

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive
from rest_framework.exceptions import APIException, ValidationError


class AuditoriaNoDisponible(APIException):
    status_code = 503
    default_detail = "No se pudo consultar la auditoría."
    default_code = "SERVICE_UNAVAILABLE"


def fecha_utc(fecha):
    return fecha.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class FiltrosAuditoria:
    page: int
    page_size: int
    desde: datetime
    hasta: datetime
    corte: datetime
    usuario_id: UUID | None = None
    accion: str | None = None

    @property
    def fin_lectura(self):
        return min(self.hasta, self.corte)


def _fecha_parametro(valor, campo):
    try:
        fecha = parse_datetime(valor)
        if fecha is None or is_naive(fecha):
            raise ValueError()
        return fecha.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValidationError({campo: ["Se requiere una fecha ISO 8601 con zona horaria."]}) from exc


def filtros_auditoria(parametros, *, corte):
    if not isinstance(corte, datetime) or is_naive(corte):
        raise AuditoriaNoDisponible()
    corte = corte.astimezone(timezone.utc)
    permitidos = {"page", "page_size", "usuario_id", "accion", "desde", "hasta"}
    errores = {}
    datos = {}
    for nombre, valores in parametros.lists():
        if nombre not in permitidos:
            errores[nombre] = ["Este parámetro no está permitido."]
        elif len(valores) != 1:
            errores[nombre] = ["El parámetro no puede repetirse."]
        else:
            datos[nombre] = valores[0]
    paginacion = {"page": 1, "page_size": 50}
    for nombre in paginacion:
        if nombre in datos:
            try:
                if not re.fullmatch(r"[0-9]+", datos[nombre]):
                    raise ValueError()
                valor = int(datos[nombre])
                if valor < 1 or (nombre == "page_size" and valor > 100):
                    raise ValueError()
                paginacion[nombre] = valor
            except ValueError:
                errores[nombre] = ["Se requiere un entero positivo dentro del rango permitido."]
    usuario_id = None
    if "usuario_id" in datos:
        try:
            usuario_id = UUID(datos["usuario_id"])
        except ValueError:
            errores["usuario_id"] = ["Se requiere un UUID de usuario."]
    accion = datos.get("accion")
    if accion is not None:
        accion = accion.strip()
        if not 1 <= len(accion) <= 100:
            errores["accion"] = ["Debe contener entre 1 y 100 caracteres."]
    if errores:
        raise ValidationError(errores)
    hasta = _fecha_parametro(datos["hasta"], "hasta") if "hasta" in datos else corte
    try:
        desde = _fecha_parametro(datos["desde"], "desde") if "desde" in datos else hasta - timedelta(days=30)
    except OverflowError as exc:
        raise ValidationError({"desde": ["El intervalo está fuera del rango permitido."]}) from exc
    if desde >= hasta or hasta - desde > timedelta(days=366):
        raise ValidationError({"desde": ["El intervalo debe ser positivo y no superar 366 días."]})
    return FiltrosAuditoria(**paginacion, desde=desde, hasta=hasta, corte=corte,
                           usuario_id=usuario_id, accion=accion)


def _uuid_publico(valor):
    if not isinstance(valor, (UUID, str)):
        raise ValueError()
    return str(UUID(str(valor)))


def _bytes_publicos(valor):
    if type(valor) is not int or not 0 <= valor <= 2**63 - 1:
        raise ValueError()
    return valor


def _tipo_elemento(valor):
    if not isinstance(valor, str) or valor not in {"archivo", "carpeta"}:
        raise ValueError()
    return valor


def _booleano(valor):
    if type(valor) is not bool:
        raise ValueError()
    return valor


def _operacion(valor):
    if valor != "AUDITORIA_ORGANIZACION" or not isinstance(valor, str):
        raise ValueError()
    return valor


def _nivel_miembro(valor):
    if type(valor) is not int or valor not in (1, 2, 3):
        raise ValueError()
    return valor


_RECURSO = {"recurso_id": _uuid_publico, "tipo_elemento": _tipo_elemento}
_DETALLES_PUBLICOS = {
    "MEMBER_ROLE_CHANGED": {"usuario_afectado_id": _uuid_publico, "nivel_anterior": _nivel_miembro, "nivel_nuevo": _nivel_miembro},
    "MEMBER_REMOVED": {"usuario_afectado_id": _uuid_publico, "nivel_anterior": _nivel_miembro},
    "USER_REGISTERED": {},
    "PASSWORD_RECOVERED": {},
    "PAPELERA_ENVIADO": _RECURSO,
    "PAPELERA_RESTAURADO": _RECURSO,
    "PAPELERA_PURGADO": {
        **_RECURSO, "bytes_fisicos_purgados": _bytes_publicos,
        "cuota_liberada_bytes": _bytes_publicos,
    },
    "PAPELERA_CARPETA_ENVIADA": {"raiz_id": _uuid_publico},
    "PAPELERA_CARPETA_RESTAURADA": {"raiz_id": _uuid_publico},
    "PAPELERA_CARPETA_PURGADA": {"raiz_id": _uuid_publico},
    "ADMIN_DATA_ACCESSED": {
        "operacion": _operacion,
        "usuario_filtro_id": _uuid_publico,
        "filtro_accion": _booleano,
    },
}


def detalles_publicos(accion, detalles):
    """Política cerrada por acción y tipo; no admite texto libre ni manifiestos.

    Motivos administrativos, claves, operaciones/generaciones técnicas y fechas
    internas se omiten en esta primera lectura organizacional.
    """
    if not isinstance(accion, str) or not isinstance(detalles, Mapping):
        return {}
    if accion == "ADMIN_DATA_ACCESSED" and (
        type(detalles.get("version")) is not int or detalles.get("version") != 1
    ):
        return {}
    salida = {}
    for nombre, convertir in _DETALLES_PUBLICOS.get(accion, {}).items():
        if nombre in detalles:
            try:
                salida[nombre] = convertir(detalles[nombre])
            except (ValueError, TypeError, AttributeError):
                pass
    return salida


def proyectar_evento(fila):
    campos = {"id", "organizacion_id", "usuario_id", "accion", "fecha_evento", "detalles"}
    if not isinstance(fila, Mapping) or not campos <= fila.keys():
        raise AuditoriaNoDisponible()
    try:
        if type(fila["id"]) is not int or not 1 <= fila["id"] <= 2**63 - 1:
            raise ValueError()
        accion = fila["accion"]
        if not isinstance(accion, str) or not 1 <= len(accion) <= 100:
            raise ValueError()
        accion.encode("utf-8")
        fecha = fila["fecha_evento"]
        if not isinstance(fecha, datetime) or is_naive(fecha):
            raise ValueError()
        return {
            "id": fila["id"],
            "organizacion_id": _uuid_publico(fila["organizacion_id"]) if fila["organizacion_id"] is not None else None,
            "usuario_id": _uuid_publico(fila["usuario_id"]) if fila["usuario_id"] is not None else None,
            "accion": accion, "fecha_evento": fecha_utc(fecha),
            "detalles": detalles_publicos(accion, fila["detalles"]),
        }
    except (ValueError, TypeError, AttributeError, OverflowError, UnicodeError) as exc:
        raise AuditoriaNoDisponible() from exc
