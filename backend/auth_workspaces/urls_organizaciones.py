"""Rutas de administración organizacional con autorización en cada vista."""

from django.urls import path

from .views_organizaciones import MiembrosOrganizacionView, GestionMiembroView
from .views_auditoria import AuditoriaOrganizacionView


from . import views_invitaciones as invitaciones


urlpatterns = [
    path("organizaciones/compartidas/", invitaciones.CrearCompartidaView.as_view(), name="organizacion-crear-compartida"),
    path("organizaciones/invitaciones/recibidas/", invitaciones.InvitacionesRecibidasView.as_view(), name="invitaciones-recibidas"),
    path("organizaciones/invitaciones/<uuid:invitacion_id>/decision/", invitaciones.DecisionInvitacionView.as_view(), name="invitacion-decision"),
    path("organizaciones/<uuid:organizacion_id>/miembros/invitar/", invitaciones.InvitarMiembroView.as_view(), name="invitacion-enviar"),
    path("organizaciones/<uuid:organizacion_id>/invitaciones/", invitaciones.InvitacionesEnviadasView.as_view(), name="invitaciones-enviadas"),
    path("organizaciones/<uuid:organizacion_id>/invitaciones/<uuid:invitacion_id>/", invitaciones.RevocarInvitacionView.as_view(), name="invitacion-revocar"),
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
