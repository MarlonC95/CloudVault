from django.contrib.auth import get_user_model

User = get_user_model()


def crear_usuario(email="mily@cloudvault.io"):
    return User.objects.create_user(
        email=email,
        password="MiClaveSegura123",
        full_name="Mily Santay",
        recovery_phrase="frase secreta de recuperacion",
    )
