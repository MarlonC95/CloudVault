from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FileMetadataViewSet, FolderViewSet

router = DefaultRouter()
router.register(r"carpetas", FolderViewSet, basename="carpeta")
router.register(r"archivos", FileMetadataViewSet, basename="archivo")

urlpatterns = [
    path("", include(router.urls)),
]
