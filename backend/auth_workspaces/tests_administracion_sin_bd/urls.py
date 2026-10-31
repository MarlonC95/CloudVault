"""Solo el URLconf de lectura bajo prueba, sin config.urls ni servicios reales."""

from django.urls import include, path


urlpatterns = [path("api/v1/", include("auth_workspaces.urls_organizaciones"))]
