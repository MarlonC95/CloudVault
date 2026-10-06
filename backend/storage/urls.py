from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FolderViewSet

router = DefaultRouter()
router.register(r"carpetas", FolderViewSet, basename="carpeta")

urlpatterns = [
    path("", include(router.urls)),
]
