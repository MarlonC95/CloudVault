"""Rutas preparadas para integración; config.urls no incluye este módulo."""

from django.urls import path

from .views_organizaciones import MiembrosOrganizacionView


urlpatterns = [
    path(
        "organizaciones/<str:organizacion_id>/miembros/",
        MiembrosOrganizacionView.as_view(),
        name="organizacion-miembros",
    ),
]
