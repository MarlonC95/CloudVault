"""Arranque con intérprete simulado; nunca lee .env ni invoca Django/S3/SQL."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

from django.test import SimpleTestCase


class ArranqueMantenimientoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Conservar fixtures locales por instrucción del usuario.
        cls.temporal = Path(mkdtemp(prefix="cv-arranque-mantenimiento-", dir="/private/tmp"))
        cls.interprete = cls.temporal / "interprete simulado"
        cls.interprete.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
print(json.dumps({"argumentos":sys.argv[1:],"directorio":os.getcwd(),
                  "intervalo":os.environ.get("ALMACENAMIENTO_MANTENIMIENTO_INTERVALO")}))
if "verificar_proveedor_almacenamiento" in sys.argv:
    raise SystemExit(int(os.environ.get("PRUEBA_FALLO_PROVEEDOR","0")))
raise SystemExit(int(os.environ.get("PRUEBA_SALIDA_MANTENIMIENTO","0")))
''')
        cls.interprete.chmod(0o700)
        cls.backend = Path(__file__).resolve().parents[2]
        cls.arranque = cls.backend / "almacenamiento/operacion/iniciar_mantenimiento.sh"

    def ejecutar(self, *argumentos, **entorno):
        return subprocess.run(["/bin/sh", str(self.arranque), *argumentos],
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                 "ALMACENAMIENTO_PYTHON": str(self.interprete), **entorno},
            cwd=self.temporal, capture_output=True, text=True, timeout=10)

    def test_sin_activacion_no_invoca_interprete(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 2)
        self.assertEqual(resultado.stdout, "")
        self.assertEqual(json.loads(resultado.stderr)["evento"], "mantenimiento_inactivo")

    def test_comprobar_solo_consulta_interfaz_sin_activar_ciclos(self):
        resultado = self.ejecutar("--comprobar")
        self.assertEqual(resultado.returncode, 0)
        registros = [json.loads(linea) for linea in resultado.stdout.splitlines()]
        self.assertEqual(len(registros), 1)
        self.assertIn("verificar_proveedor_almacenamiento", registros[0]["argumentos"])

    def test_proveedor_incompatible_impide_iniciar_mantenimiento(self):
        resultado = self.ejecutar(ALMACENAMIENTO_MANTENIMIENTO_HABILITADO="1",
                                  PRUEBA_FALLO_PROVEEDOR="7")
        self.assertEqual(resultado.returncode, 7)
        self.assertEqual(len(resultado.stdout.splitlines()), 1)
        self.assertNotIn('"mantener_cargas"', resultado.stdout)

    def test_arranque_valida_proveedor_y_hereda_intervalo_en_backend(self):
        resultado = self.ejecutar(ALMACENAMIENTO_MANTENIMIENTO_HABILITADO="1",
                                  ALMACENAMIENTO_MANTENIMIENTO_INTERVALO="90")
        self.assertEqual(resultado.returncode, 0)
        registros = [json.loads(linea) for linea in resultado.stdout.splitlines()]
        self.assertEqual([r["argumentos"][2] for r in registros],
                         ["verificar_proveedor_almacenamiento", "mantener_cargas"])
        self.assertIn("--continuo", registros[1]["argumentos"])
        self.assertTrue(all(r["intervalo"] == "90" for r in registros))
        self.assertTrue(all(Path(r["directorio"]).resolve() == self.backend for r in registros))

    def test_codigo_del_worker_se_entrega_al_supervisor(self):
        resultado = self.ejecutar(ALMACENAMIENTO_MANTENIMIENTO_HABILITADO="1",
                                  PRUEBA_SALIDA_MANTENIMIENTO="23")
        self.assertEqual(resultado.returncode, 23)

    def test_argumentos_no_admitidos_no_inician_interprete(self):
        resultado = self.ejecutar("--continuo")
        self.assertEqual(resultado.returncode, 2)
        self.assertEqual(resultado.stdout, "")
