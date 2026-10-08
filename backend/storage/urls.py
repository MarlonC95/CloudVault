from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ArchivoViewSet, CarpetaViewSet

router = DefaultRouter()
router.register(r"carpetas", CarpetaViewSet, basename="carpeta")
router.register(r"archivos", ArchivoViewSet, basename="archivo")

urlpatterns = [
    path("", include(router.urls)),
]
