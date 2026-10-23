"""El controlador privado consume SQL delegado y registra su origen exacto."""

import hashlib
from io import StringIO
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from almacenamiento.tests_persistencia import aceptacion, ejecutar, esquema_externo


class EsquemaExternoTests(SimpleTestCase):
    def test_referencia_se_fija_a_commit_antes_de_leer_sin_checkout_o_fetch(self):
        commit = "a" * 40
        contenido = b"esquema sintetico de ensayo"
        with patch.object(esquema_externo.subprocess, "run", side_effect=[
                SimpleNamespace(stdout=commit + "\n"), SimpleNamespace(stdout=contenido)]) as git:
            texto, fuente = esquema_externo.cargar_esquema(Path("/repo"))
        self.assertEqual(texto, contenido.decode())
        self.assertEqual(fuente["commit"], commit)
        self.assertEqual(fuente["sha256"], hashlib.sha256(contenido).hexdigest())
        self.assertEqual(git.call_args_list[1].args[0], ["git", "show", commit + ":database/schema.sql"])
        self.assertEqual([c.args[0][1] for c in git.call_args_list], ["rev-parse", "show"])
        self.assertEqual(git.call_args.kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")

    def test_archivo_externo_se_lee_sin_git_y_sin_publicar_ruta_privada(self):
        with patch.object(Path, "read_bytes", return_value=b"esquema de prueba"), \
                patch.object(esquema_externo.subprocess, "run") as git:
            _, fuente = esquema_externo.cargar_esquema(Path("/repo"), archivo="/privado/schema.txt")
        self.assertEqual(fuente["tipo"], "archivo_externo")
        self.assertEqual(fuente["nombre"], "schema.txt")
        self.assertNotIn("privado", str(fuente))
        git.assert_not_called()

    def test_fuentes_vacias_ilegibles_y_no_utf8_no_arrancan_postgres(self):
        for contenido in (b"", b"  \n", b"\xff"):
            with self.subTest(contenido=contenido), \
                    patch.object(Path, "read_bytes", return_value=contenido), self.assertRaises(ValueError):
                esquema_externo.cargar_esquema(Path("/repo"), archivo="esquema.txt")
        with patch.object(Path, "read_bytes", side_effect=OSError("synthetic-private")), \
                self.assertRaises(ValueError) as error:
            esquema_externo.cargar_esquema(Path("/repo"), archivo="esquema.txt")
        self.assertNotIn("synthetic-private", str(error.exception))

    def test_ruta_y_referencia_invalidas_no_invocan_git(self):
        for referencia, ruta in (("-opcion", "schema.sql"), ("rama\nsegunda", "schema.sql"),
                                 ("rama", "../schema.sql"), ("rama", "/schema.sql")):
            with self.subTest(referencia=referencia, ruta=ruta), \
                    patch.object(esquema_externo.subprocess, "run") as git, self.assertRaises(ValueError):
                esquema_externo.cargar_esquema(Path("/repo"), referencia=referencia, ruta=ruta)
            git.assert_not_called()

    def test_fuente_ausente_aborta_antes_de_crear_cluster_o_conectar(self):
        with patch("sys.argv", ["ejecutar"]), \
                patch.object(ejecutar, "cargar_esquema", side_effect=ValueError("Esquema externo ausente")), \
                patch.object(ejecutar, "mkdtemp") as temporal, \
                patch.object(ejecutar.psycopg, "connect") as conectar, \
                patch("sys.stderr", StringIO()), self.assertRaises(SystemExit) as error:
            ejecutar.main()
        self.assertEqual(error.exception.code, 2)
        temporal.assert_not_called()
        conectar.assert_not_called()

    def test_tabla14_debe_estar_en_esquema_privado_sin_recrearla(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = (False,)
        with self.assertRaises(ValueError):
            esquema_externo.verificar_diario(conn)
        conn.execute.assert_called_once_with(
            "SELECT to_regclass('public.trabajos_mantenimiento') IS NOT NULL")

    def test_evidencia_no_depende_de_documentos_personales_en_clon_limpio(self):
        repo = Path(mkdtemp(prefix="cv-evidencia-test-", dir="/private/tmp"))
        modulo = repo / "backend/almacenamiento"
        modulo.mkdir(parents=True)
        (modulo / "ejemplo.py").write_text("# ensayo\n")
        with patch.object(aceptacion.subprocess, "run", return_value=SimpleNamespace(stdout="a" * 40)):
            informe = aceptacion.metadatos(repo)
        self.assertEqual(list(informe["hashes"]), ["backend/almacenamiento/ejemplo.py"])
        self.assertEqual(len(informe["referencias_locales_ausentes"]), 2)
