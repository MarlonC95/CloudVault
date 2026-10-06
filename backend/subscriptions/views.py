from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from common.pagination import EnvelopePagination
from common.responses import fail, ok
from storage.services import get_used_bytes

from . import services
from .models import Plan, Subscription

TIPOS_FACTURACION = {
    Subscription.TipoFacturacion.MENSUAL,
    Subscription.TipoFacturacion.ANUAL,
}


def _obtener_o_crear_gratuito(usuario):
    suscripcion = getattr(usuario, "suscripcion", None)
    if suscripcion is not None:
        return suscripcion
    plan = Plan.objects.get(slug="gratuito")
    ahora = timezone.now()
    return Subscription.objects.create(
        usuario=usuario,
        plan=plan,
        tipo_facturacion=Subscription.TipoFacturacion.MENSUAL,
        periodo_inicio=ahora,
        periodo_fin=services.sumar_meses(ahora, 1),
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def planes(request):
    """§10.1 — Catálogo de planes."""
    paginador = EnvelopePagination()
    pagina = paginador.paginate_queryset(Plan.objects.filter(activo=True), request)
    return paginador.get_paginated_response([services.plan_publico(plan) for plan in pagina])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mi_plan(request):
    """§10.2 — Plan actual y consumo; sin suscripción crea el plan gratuito."""
    suscripcion = _obtener_o_crear_gratuito(request.user)
    plan = suscripcion.plan
    usado = get_used_bytes(request.user)
    return ok({
        "plan": {
            "id": plan.slug,
            "nombre": plan.nombre,
            "precio_mensual": services.numero(plan.precio_mensual),
            "tipo_facturacion": suscripcion.tipo_facturacion,
        },
        "estado": suscripcion.estado,
        "renueva_en": services.fecha_iso(suscripcion.periodo_fin),
        "almacenamiento": services.bloque_almacenamiento(usado, plan.almacenamiento_bytes),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def suscribir(request):
    """§10.3 — Contratar o cambiar de plan (pago simulado)."""
    plan_id = request.data.get("plan_id")
    tipo_facturacion = request.data.get("tipo_facturacion")
    fields = {}

    plan = None
    if isinstance(plan_id, str) and plan_id:
        plan = Plan.objects.filter(slug=plan_id, activo=True).first()
    if plan is None:
        fields["plan_id"] = ["El plan indicado no existe."]
    if tipo_facturacion not in TIPOS_FACTURACION:
        fields["tipo_facturacion"] = ["El tipo de facturación debe ser 'mensual' o 'anual'."]
    if fields:
        return fail("VALIDATION_ERROR", fields)

    usado = get_used_bytes(request.user)
    cuota = plan.almacenamiento_bytes
    if cuota is not None and usado > cuota:
        return fail(
            "CUOTA_EXCEDIDA",
            {"plan_id": ["Tu uso actual supera la cuota del nuevo plan."]},
            status=409,
        )

    ahora = timezone.now()
    meses = 12 if tipo_facturacion == Subscription.TipoFacturacion.ANUAL else 1
    suscripcion, _ = Subscription.objects.update_or_create(
        usuario=request.user,
        defaults={
            "plan": plan,
            "estado": Subscription.Estado.ACTIVO,
            "tipo_facturacion": tipo_facturacion,
            "periodo_inicio": ahora,
            "periodo_fin": services.sumar_meses(ahora, meses),
        },
    )
    return ok({
        "plan": {
            "id": plan.slug,
            "nombre": plan.nombre,
            "tipo_facturacion": suscripcion.tipo_facturacion,
        },
        "estado": suscripcion.estado,
        "renueva_en": services.fecha_iso(suscripcion.periodo_fin),
    })
