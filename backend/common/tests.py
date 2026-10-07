from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from common.ambito import resolver_organizacion
from common.formatting import bytes_legibles
from common.testing import (
    agregar_miembro, crear_organizacion, crear_usuario, espacio_de_trabajo,
)


class _Usuario:
    def __init__(self, pk):
        self.pk = pk


class FormatoTamanoTests(SimpleTestCase):
    def test_formato_del_contrato_con_punto_decimal(self):
        casos = {0: "0 B", 840 * 1024: "840 KB", 4404019: "4.2 MB",
                 128 * 1024**2: "128 MB", 1503238554: "1.4 GB", 1048575 * 1024: "1 GB"}
        for valor, esperado in casos.items():
            self.assertEqual(bytes_legibles(valor), esperado, valor)


class EsquemaSqlTests(TestCase):
    def test_runner_instala_planes_y_trigger_de_cuota(self):
        from django.db import connection

        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM planes")
            self.assertEqual(c.fetchone()[0], 3)
            usuario_id, org_id = espacio_de_trabajo()
            c.execute(
                """INSERT INTO archivos (organizacion_id, propietario_id, nombre_original,
                   clave_s3, tamano_bytes, tipo_mime) VALUES (%s, %s, 'a.txt', 'k-test', 1000, 'text/plain')""",
                [org_id, usuario_id],
            )
            c.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id=%s", [org_id])
            self.assertEqual(c.fetchone()[0], 1000)


class ResolverOrganizacionTests(TestCase):
    def test_unica_membresia(self):
        usuario_id, org_id = espacio_de_trabajo(nivel_rol=2)
        ambito = resolver_organizacion(_Usuario(usuario_id))
        self.assertEqual((ambito.organizacion_id, ambito.nivel_rol), (org_id, 2))

    def test_sin_membresia_es_403(self):
        with self.assertRaises(PermissionDenied):
            resolver_organizacion(_Usuario(crear_usuario()))

    def test_varias_membresias_exigen_organizacion(self):
        usuario_id, org_id = espacio_de_trabajo()
        otra = crear_organizacion()
        agregar_miembro(otra, usuario_id, 1)
        with self.assertRaises(ValidationError):
            resolver_organizacion(_Usuario(usuario_id))
        self.assertEqual(resolver_organizacion(_Usuario(usuario_id), otra).organizacion_id, otra)

    def test_organizacion_ajena_es_404(self):
        usuario_id, _ = espacio_de_trabajo()
        with self.assertRaises(NotFound):
            resolver_organizacion(_Usuario(usuario_id), crear_organizacion())

    def test_organizacion_invalida_es_400(self):
        usuario_id, _ = espacio_de_trabajo()
        with self.assertRaises(ValidationError):
            resolver_organizacion(_Usuario(usuario_id), "no-es-uuid")

    def test_lector_no_escribe(self):
        usuario_id, _ = espacio_de_trabajo(nivel_rol=1)
        resolver_organizacion(_Usuario(usuario_id))
        with self.assertRaises(PermissionDenied):
            resolver_organizacion(_Usuario(usuario_id), escritura=True)

    def test_organizacion_inactiva_no_cuenta(self):
        usuario_id = crear_usuario()
        inactiva = crear_organizacion(activa=False)
        agregar_miembro(inactiva, usuario_id, 0)
        with self.assertRaises(PermissionDenied):
            resolver_organizacion(_Usuario(usuario_id))


class AutenticacionConUsuariosSqlTests(TestCase):
    """El JWT de auth_workspaces debe resolver al Usuario sobre la tabla ``usuarios``."""

    def test_token_valido_resuelve_usuario(self):
        from uuid import uuid4

        from common.testing import cliente_autenticado

        usuario_id, _ = espacio_de_trabajo()
        respuesta = cliente_autenticado(usuario_id).get(f"/api/v1/archivos/{uuid4()}/descarga/")
        # 503 = autenticado, pero aún sin ALMACENAMIENTO_SERVICIOS_FACTORY (llega en el Run 4).
        self.assertNotIn(respuesta.status_code, (401, 500), respuesta.content)
