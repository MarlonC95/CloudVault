"""Rutas de administración organizacional con autorización en cada vista."""

from django.urls import path

from .views_organizaciones import MiembrosOrganizacionView, GestionMiembroView
from .views_auditoria import AuditoriaOrganizacionView


urlpatterns = [
    path("organizaciones/<str:organizacion_id>/miembros/<str:usuario_id>/", GestionMiembroView.as_view(), name="organizacion-miembro"),
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
