from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArchivoViewSet, CarpetaViewSet, PapeleraCarpetasView, PapeleraViewSet,
    OperacionVaciadoPapeleraView, PurgarCarpetaPapeleraView,
    RestaurarCarpetaPapeleraView, ResumenUnidadView, VaciadoPapeleraView,
)

router = DefaultRouter()
router.register(r"carpetas", CarpetaViewSet, basename="carpeta")
router.register(r"archivos", ArchivoViewSet, basename="archivo")
router.register(r"papelera", PapeleraViewSet, basename="papelera")

urlpatterns = [
    path("unidad/resumen/", ResumenUnidadView.as_view(), name="unidad-resumen"),
    path("papelera/carpetas/", PapeleraCarpetasView.as_view(), name="papelera-carpetas"),
    path("papelera/carpetas/<uuid:pk>/restaurar/",
         RestaurarCarpetaPapeleraView.as_view(), name="papelera-carpetas-restaurar"),
    path("papelera/carpetas/<uuid:pk>/", PurgarCarpetaPapeleraView.as_view(),
         name="papelera-carpetas-purgar"),
    path("papelera/vaciar/", VaciadoPapeleraView.as_view(), name="papelera-vaciar"),
    path("papelera/vaciados/<uuid:operacion_id>/",
         OperacionVaciadoPapeleraView.as_view(), name="papelera-vaciado-operacion"),
    path("", include(router.urls)),
]
