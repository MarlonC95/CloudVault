"""Fixtures para pruebas sobre el esquema SQL real (tablas ``managed = False``).

Insertan con SQL directo porque Django no crea estas tablas; el esquema y los
triggers los instala ``common.test_runner``.
"""

from datetime import timedelta
from uuid import uuid4

from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from auth_workspaces.models import Usuario

HASH_PRUEBA = "pbkdf2_sha256$1$prueba$hash-sintetico"
PLAN_GRATUITO, PLAN_PRO, PLAN_EMPRESARIAL = 1, 2, 3  # ids de database/seeds.sql


def crear_usuario(correo=None, nombre="Usuario Prueba", using="default"):
    uid = uuid4()
    correo = correo or f"{uid}@example.test"
    with connections[using].cursor() as c:
        c.execute(
            """INSERT INTO usuarios
               (id, nombre_completo, correo_electronico, contrasena_hash, palabra_secreta_hash)
               VALUES (%s, %s, %s, %s, %s)""",
            [uid, nombre, correo, HASH_PRUEBA, HASH_PRUEBA],
        )
    return uid


def crear_organizacion(nombre="Organización de prueba", using="default"):
    oid = uuid4()
    with connections[using].cursor() as c:
        c.execute(
            "INSERT INTO organizaciones (id, nombre, slug) VALUES (%s, %s, %s)",
            [oid, nombre, f"org-{oid}"],
        )
    return oid


def agregar_miembro(organizacion_id, usuario_id, nivel_rol=0, using="default"):
    with connections[using].cursor() as c:
        c.execute(
            """INSERT INTO miembros_organizacion (organizacion_id, usuario_id, nivel_rol)
               VALUES (%s, %s, %s)""",
            [organizacion_id, usuario_id, nivel_rol],
        )


def crear_suscripcion(organizacion_id, plan_id=PLAN_GRATUITO, estado="ACTIVE",
                      intervalo="MONTHLY", dias=30, using="default"):
    sid = uuid4()
    ahora = timezone.now()
    with connections[using].cursor() as c:
        c.execute(
            """INSERT INTO suscripciones
               (id, organizacion_id, plan_id, estado, intervalo, periodo_inicio, periodo_fin)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [sid, organizacion_id, plan_id, estado, intervalo, ahora, ahora + timedelta(days=dias)],
        )
    return sid


def espacio_de_trabajo(nivel_rol=0, plan_id=PLAN_GRATUITO):
    """Usuario + organización + membresía + suscripción activa. Devuelve (usuario_id, organizacion_id)."""
    usuario_id = crear_usuario()
    organizacion_id = crear_organizacion()
    agregar_miembro(organizacion_id, usuario_id, nivel_rol)
    crear_suscripcion(organizacion_id, plan_id)
    return usuario_id, organizacion_id


def cliente_autenticado(usuario_id):
    """APIClient con un access token válido para ``usuario_id`` (sin pasar por el login)."""
    usuario = Usuario(id=usuario_id, correo_electronico="prueba@example.test", password=HASH_PRUEBA)
    token = RefreshToken.for_user(usuario).access_token
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return cliente
