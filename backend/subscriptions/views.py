"""Endpoints de suscripciones (§10.1-§10.4) sobre el esquema SQL real.

La suscripción pertenece a la organización; el ámbito se resuelve con
``resolver_organizacion`` y solo el propietario (nivel_rol 0) puede contratar.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.ambito import resolver_organizacion
from common.errores import ContratoAPIMixin
from common.pagination import EnvelopePagination
from common.responses import fail, ok

from . import services
from .cuotas import SinSuscripcionVigente, leer_cuota_organizacion
from .models import HistorialPago, Organizacion, Plan, Suscripcion


class PlanesView(ContratoAPIMixin, APIView):
    """§10.1 — Catálogo de planes activos, ordenado por id."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Catálogo paginado de planes activos.")},
        tags=["Suscripciones"],
    )
    def get(self, request):
        planes = Plan.objects.filter(esta_activo=True).order_by("id")
        paginador = EnvelopePagination()
        pagina = paginador.paginate_queryset(planes, request)
        return paginador.get_paginated_response(
            [services.plan_publico(plan) for plan in pagina]
        )


class MiPlanView(ContratoAPIMixin, APIView):
    """§10.2 — Plan y consumo de la organización; no crea suscripciones."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Plan y consumo de la organización.")},
        tags=["Suscripciones"],
    )
    def get(self, request):
        ambito = resolver_organizacion(
            request.user, request.query_params.get("organizacion_id")
        )
        try:
            limite_bytes, usado_bytes, periodo_fin = leer_cuota_organizacion(
                ambito.organizacion_id
            )
        except SinSuscripcionVigente:
            return fail("CONTEXT_NOT_READY", status=409)

        suscripcion = (
            Suscripcion.objects.select_related("plan")
            .filter(organizacion_id=ambito.organizacion_id, estado=Suscripcion.ESTADO_ACTIVE)
            .order_by("-periodo_inicio")
            .first()
        )
        plan = suscripcion.plan
        return ok({
            "plan": {
                "id": services.id_publico(plan.id),
                "nombre": services.nombre_mostrado(plan.nombre),
                "precio_mensual": services.numero(plan.precio),
                "tipo_facturacion": services.intervalo_a_cliente(suscripcion.intervalo),
            },
            "estado": suscripcion.estado,
            "renueva_en": services.fecha_iso(periodo_fin),
            "almacenamiento": services.bloque_almacenamiento(usado_bytes, limite_bytes),
        })


class SuscribirView(ContratoAPIMixin, APIView):
    """§10.3 — Contratar o cambiar de plan (pago simulado); solo propietario."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            "SuscribirPlanEntrada",
            fields={
                "plan_id": serializers.CharField(help_text="gratuito, pro o empresarial"),
                "tipo_facturacion": serializers.ChoiceField(choices=["mensual", "anual"]),
                "organizacion_id": serializers.UUIDField(required=False),
            },
        ),
        responses={200: OpenApiResponse(description="Suscripción actualizada.")},
        tags=["Suscripciones"],
    )
    def post(self, request):
        ambito = resolver_organizacion(
            request.user, request.data.get("organizacion_id"), escritura=True
        )
        if not ambito.es_admin:
            raise PermissionDenied()

        fields = {}
        plan_id = services.plan_id_desde_codigo(request.data.get("plan_id"))
        plan = Plan.objects.filter(id=plan_id, esta_activo=True).first() if plan_id else None
        if plan is None:
            fields["plan_id"] = ["El plan indicado no existe."]

        intervalo = services.intervalo_desde_cliente(request.data.get("tipo_facturacion"))
        if intervalo is None:
            fields["tipo_facturacion"] = [
                "El tipo de facturación debe ser 'mensual' o 'anual'."
            ]
        if fields:
            return fail("VALIDATION_ERROR", fields)

        usado = (
            Organizacion.objects.filter(id=ambito.organizacion_id)
            .values_list("almacenamiento_usado_bytes", flat=True)
            .first()
        ) or 0
        if usado > plan.limite_almacenamiento_bytes:
            return fail(
                "CUOTA_EXCEDIDA",
                {"plan_id": ["Tu uso actual supera la cuota del nuevo plan."]},
                status=409,
            )

        ahora = timezone.now()
        meses = 12 if intervalo == Suscripcion.INTERVALO_ANUAL else 1
        suscripcion = (
            Suscripcion.objects.filter(
                organizacion_id=ambito.organizacion_id, estado=Suscripcion.ESTADO_ACTIVE
            )
            .order_by("-periodo_inicio")
            .first()
        )
        if suscripcion is None:
            suscripcion = Suscripcion(organizacion_id=ambito.organizacion_id)
        suscripcion.plan = plan
        suscripcion.estado = Suscripcion.ESTADO_ACTIVE
        suscripcion.intervalo = intervalo
        suscripcion.periodo_inicio = ahora
        suscripcion.periodo_fin = services.sumar_meses(ahora, meses)
        suscripcion.auto_renovar = True
        suscripcion.save()

        monto = services.precio_anual(plan.precio) if intervalo == Suscripcion.INTERVALO_ANUAL else plan.precio
        HistorialPago.objects.create(
            suscripcion=suscripcion,
            monto=monto,
            estado="COMPLETED",
            referencia_transaccion=f"sim-{services.token_aleatorio()}",
            fecha_pago=ahora,
        )

        return ok({
            "plan": {
                "id": services.id_publico(plan.id),
                "nombre": services.nombre_mostrado(plan.nombre),
                "tipo_facturacion": services.intervalo_a_cliente(suscripcion.intervalo),
            },
            "estado": suscripcion.estado,
            "renueva_en": services.fecha_iso(suscripcion.periodo_fin),
        })


class FacturasView(ContratoAPIMixin, APIView):
    """§10.4 — Historial de pagos de la suscripción activa."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Historial paginado de pagos.")},
        tags=["Suscripciones"],
    )
    def get(self, request):
        ambito = resolver_organizacion(
            request.user, request.query_params.get("organizacion_id")
        )
        suscripcion = (
            Suscripcion.objects.filter(
                organizacion_id=ambito.organizacion_id, estado=Suscripcion.ESTADO_ACTIVE
            )
            .order_by("-periodo_inicio")
            .values_list("id", flat=True)
            .first()
        )
        if suscripcion is None:
            return fail("CONTEXT_NOT_READY", status=409)

        pagos = (
            HistorialPago.objects.filter(suscripcion_id=suscripcion)
            .select_related("suscripcion")
            .order_by("-fecha_pago")
        )
        paginador = EnvelopePagination()
        pagina = paginador.paginate_queryset(pagos, request)
        return paginador.get_paginated_response(
            [services.factura_publica(pago) for pago in pagina]
        )
