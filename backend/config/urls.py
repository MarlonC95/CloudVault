"""API routes."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from auth_workspaces.views import server_error
from almacenamiento.rutas_integracion import rutas_almacenamiento_y_negocio


urlpatterns = [
    path("api/v1/auth/", include("auth_workspaces.urls")),
    *rutas_almacenamiento_y_negocio(),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

handler500 = server_error
