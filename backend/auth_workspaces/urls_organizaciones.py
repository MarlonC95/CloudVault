"""Rutas preparadas para integración; config.urls no incluye este módulo."""

from django.urls import path

from .views_organizaciones import MiembrosOrganizacionView
from .views_auditoria import AuditoriaOrganizacionView


urlpatterns = [
    path(
        "organizaciones/<str:organizacion_id>/auditoria/",
        AuditoriaOrganizacionView.as_view(),
        name="organizacion-auditoria",
    ),
    path(
        "organizaciones/<str:organizacion_id>/miembros/",
        MiembrosOrganizacionView.as_view(),
        name="organizacion-miembros",
    ),
]
