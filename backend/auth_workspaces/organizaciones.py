"""Lectura acotada de miembros sobre las tablas existentes, sin escrituras."""

from dataclasses import dataclass

from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from subscriptions.models import MiembroOrganizacion

from .models import Usuario


ROLES_ORGANIZACION = {
    0: "PROPIETARIO",
    1: "LECTOR_NV1",
    2: "OPERATIVO_NV2",
    3: "AVANZADO_NV3",
}


class LecturaMiembrosNoDisponible(APIException):
    status_code = 503
    default_detail = "No se pudo consultar la organización."
    default_code = "SERVICE_UNAVAILABLE"


@dataclass(frozen=True)
class PaginaMiembros:
    count: int
    page: int
    page_size: int
    results: list[dict]


def listar_miembros(organizacion_id, *, page, page_size):
    """Requiere autorización previa y paginación validada por la vista.

    El UUID de usuario no es una FK ORM en MiembroOrganizacion. Se resuelven
    los datos públicos por lote, limitado a los usuarios de la página.
    """
    miembros = MiembroOrganizacion.objects.filter(
        organizacion_id=organizacion_id,
    ).order_by("fecha_union", "usuario_id")
    count = miembros.count()
    ultima = max(1, (count + page_size - 1) // page_size)
    if page > ultima:
        raise ValidationError({"page": ["La página solicitada no existe."]})

    inicio = (page - 1) * page_size
    filas = list(miembros[inicio:inicio + page_size].values(
        "usuario_id", "nivel_rol", "fecha_union",
    ))
    ids = {fila["usuario_id"] for fila in filas}
    usuarios = {
        fila["id"]: fila
        for fila in Usuario.objects.filter(pk__in=ids).values(
            "id", "nombre_completo", "correo_electronico",
        )
    } if ids else {}

    resultados = []
    for fila in filas:
        usuario = usuarios.get(fila["usuario_id"])
        nivel = fila["nivel_rol"]
        fecha = fila["fecha_union"]
        if (usuario is None or type(nivel) is not int
                or nivel not in ROLES_ORGANIZACION
                or fecha is None or timezone.is_naive(fecha)):
            raise LecturaMiembrosNoDisponible()
        resultados.append({
            "usuario_id": fila["usuario_id"],
            "nombre_completo": usuario["nombre_completo"],
            "correo_electronico": usuario["correo_electronico"],
            "rol": ROLES_ORGANIZACION[nivel],
            "nivel_rol": nivel,
            "fecha_ingreso": fecha,
        })
    return PaginaMiembros(count, page, page_size, resultados)
