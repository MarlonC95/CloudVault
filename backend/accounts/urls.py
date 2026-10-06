from django.urls import path
from .views import login, recover_password, register

urlpatterns = [
    path("registro/", register, name="registro"),
    path("login/", login, name="login"),
    path("recuperar-contrasena/", recover_password, name="recuperar-contrasena"),
]
