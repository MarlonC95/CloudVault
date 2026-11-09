from django.urls import path

from .espacios_disponibles import EspaciosDisponiblesView

urlpatterns = [
    path("organizaciones/disponibles/", EspaciosDisponiblesView.as_view(), name="espacios-disponibles"),
]
