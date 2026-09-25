from django.urls import path

from .views import LoginView, RecuperarContrasenaView, RegistroView


urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", LoginView.as_view(), name="login"),
    path("recuperar-contrasena/", RecuperarContrasenaView.as_view(), name="recuperar-contrasena"),
]
