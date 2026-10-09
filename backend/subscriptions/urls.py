from django.urls import path

from .views import FacturasView, MiPlanView, PlanesView, SuscribirView

app_name = "subscriptions"
urlpatterns = [
    path("planes/", PlanesView.as_view(), name="planes"),
    path("mi-plan/", MiPlanView.as_view(), name="mi-plan"),
    path("mi-plan/suscribir/", SuscribirView.as_view(), name="mi-plan-suscribir"),
    path("mi-plan/facturas/", FacturasView.as_view(), name="mi-plan-facturas"),
]
