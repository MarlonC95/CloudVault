from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ArchivoViewSet, CarpetaViewSet, PapeleraViewSet, ResumenUnidadView

router = DefaultRouter()
router.register(r"carpetas", CarpetaViewSet, basename="carpeta")
router.register(r"archivos", ArchivoViewSet, basename="archivo")
router.register(r"papelera", PapeleraViewSet, basename="papelera")

urlpatterns = [
    path("unidad/resumen/", ResumenUnidadView.as_view(), name="unidad-resumen"),
    path("", include(router.urls)),
]
