from django.urls import path

from .views import mi_plan, planes, suscribir

urlpatterns = [
    path("planes/", planes, name="planes"),
    path("mi-plan/", mi_plan, name="mi-plan"),
    path("mi-plan/suscribir/", suscribir, name="mi-plan-suscribir"),
]
