"""Regresión del volumen node_modules al reconstruir el frontend."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"


class DockerEntrypointTests(unittest.TestCase):
    def test_actualiza_dependencias_cuando_cambia_el_lockfile(self):
        with tempfile.TemporaryDirectory(prefix="cloudvault-frontend-test-") as directory:
            app = Path(directory)
            (app / "node_modules").mkdir()
            (app / "package-lock.json").write_text('{"version": 2}\n')
            marker = app / "node_modules/.cloudvault-package-lock.json"
            marker.write_text('{"version": 1}\n')
            binaries = app / "bin"
            binaries.mkdir()
            npm = binaries / "npm"
            npm.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$NPM_CALLS"\n')
            npm.chmod(0o700)
            calls = app / "npm-calls"
            result = subprocess.run(
                ["sh", str(ENTRYPOINT), "sh", "-c", "printf command-executed"],
                cwd=app,
                env={**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}", "NPM_CALLS": str(calls)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["ci --no-audit --no-fund"])
            self.assertEqual(marker.read_bytes(), (app / "package-lock.json").read_bytes())
            self.assertEqual(result.stdout, "command-executed")

    def test_lockfile_vigente_no_reinstala_y_conserva_codigo_de_salida(self):
        with tempfile.TemporaryDirectory(prefix="cloudvault-frontend-test-") as directory:
            app = Path(directory)
            (app / "node_modules").mkdir()
            lockfile = '{"version": 1}\n'
            (app / "package-lock.json").write_text(lockfile)
            (app / "node_modules/.cloudvault-package-lock.json").write_text(lockfile)
            binaries = app / "bin"
            binaries.mkdir()
            npm = binaries / "npm"
            npm.write_text('#!/bin/sh\nprintf called > "$NPM_CALLS"\nexit 99\n')
            npm.chmod(0o700)
            calls = app / "npm-calls"
            result = subprocess.run(
                ["sh", str(ENTRYPOINT), "sh", "-c", "exit 7"],
                cwd=app,
                env={**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}", "NPM_CALLS": str(calls)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()
