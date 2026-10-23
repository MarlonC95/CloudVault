from django.urls import path

from .views import (
    CambiarContrasenaView,
    LoginView,
    LogoutView,
    PerfilView,
    RecuperarContrasenaView,
    RefreshView,
    RegistroView,
)

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", LoginView.as_view(), name="login"),
    path("recuperar-contrasena/", RecuperarContrasenaView.as_view(), name="recuperar-contrasena"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("cambiar-contrasena/", CambiarContrasenaView.as_view(), name="cambiar-contrasena"),
]
