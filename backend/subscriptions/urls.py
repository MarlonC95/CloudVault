from django.urls import path

from .views import (
    FacturasView, MiPlanView, PlanesView, SuscribirView, TarjetaDetalleView, TarjetasView,
)

app_name = "subscriptions"
urlpatterns = [
    path("planes/", PlanesView.as_view(), name="planes"),
    path("mi-plan/", MiPlanView.as_view(), name="mi-plan"),
    path("mi-plan/suscribir/", SuscribirView.as_view(), name="mi-plan-suscribir"),
    path("mi-plan/facturas/", FacturasView.as_view(), name="mi-plan-facturas"),
    path("mi-plan/tarjetas/", TarjetasView.as_view(), name="mi-plan-tarjetas"),
    path(
        "mi-plan/tarjetas/<uuid:tarjeta_id>/",
        TarjetaDetalleView.as_view(),
        name="mi-plan-tarjeta",
    ),
]
