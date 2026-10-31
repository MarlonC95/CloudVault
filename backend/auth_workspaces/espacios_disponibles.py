"""Descubrimiento de membresías existentes; no identifica ni crea espacios personales."""

from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from subscriptions.models import MiembroOrganizacion, Organizacion

from .organizaciones import LecturaMiembrosNoDisponible, ROLES_ORGANIZACION
from .permisos_administracion import _cuenta_vigente
from .views_organizaciones import MiembrosOrganizacionView, _paginacion, _enlace


def listar_espacios(usuario, *, page, page_size):
    cuenta = _cuenta_vigente(usuario)
    miembros = MiembroOrganizacion.objects.filter(usuario_id=cuenta.pk).order_by(
        "fecha_union", "organizacion_id")
    count = miembros.count()
    if page > max(1, (count + page_size - 1) // page_size):
        raise ValidationError({"page": ["La página solicitada no existe."]})
    inicio = (page - 1) * page_size
    filas = list(miembros[inicio:inicio + page_size].values("organizacion_id", "nivel_rol"))
    nombres = dict(Organizacion.objects.filter(
        pk__in={f["organizacion_id"] for f in filas},
    ).values_list("id", "nombre")) if filas else {}
    resultados = []
    for fila in filas:
        nivel = fila["nivel_rol"]
        org = fila["organizacion_id"]
        if type(nivel) is not int or nivel not in ROLES_ORGANIZACION or org not in nombres:
            raise LecturaMiembrosNoDisponible()
        resultados.append({"id": str(org), "nombre": nombres[org], "nivel_rol": nivel})
    return count, resultados


class EspaciosDisponiblesView(MiembrosOrganizacionView):
    """Ruta estrecha independiente de las propuestas de administración del PDF."""

    def get(self, request):
        paginacion = _paginacion(request)
        count, resultados = listar_espacios(request.user, **paginacion)
        page, size = paginacion["page"], paginacion["page_size"]
        respuesta = Response({"data": {
            "count": count, "page_size": size, "results": resultados,
            "next": _enlace(request, page + 1 if page * size < count else None, size),
            "previous": _enlace(request, page - 1 if page > 1 else None, size),
        }})
        respuesta["Cache-Control"] = "no-store"
        return respuesta
