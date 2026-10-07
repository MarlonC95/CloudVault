from django.urls import path

from .views import ConfirmarCargaView, DescargaView, IniciarCargaView

app_name = "almacenamiento"
urlpatterns = [
    path("iniciar-carga/", IniciarCargaView.as_view(), name="iniciar-carga"),
    path("<str:id>/confirmar-carga/", ConfirmarCargaView.as_view(), name="confirmar-carga"),
    path("<str:id>/descarga/", DescargaView.as_view(), name="descarga"),
]
