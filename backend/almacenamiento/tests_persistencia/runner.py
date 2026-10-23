import os
import json
from pathlib import Path
from time import monotonic
from unittest import TextTestResult

from django.db import connection, connections
from django.test.runner import DiscoverRunner


class ResultadoConEvidencia(TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evidencia = []

    def startTest(self, test):
        super().startTest(test)
        self.actual = {"id": test.id(), "estado": "BLOQUEADO"}
        self.subprueba_omitida = False
        self.inicio = monotonic()

    def addSuccess(self, test):
        super().addSuccess(test)
        if not self.subprueba_omitida and self.actual["estado"] != "FALLIDO":
            self.actual["estado"] = "APROBADO"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.subprueba_omitida = True

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.actual["estado"] = "FALLIDO"

    def addError(self, test, err):
        super().addError(test, err)
        self.actual["estado"] = "FALLIDO"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.actual["estado"] = "FALLIDO"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.actual["estado"] = "FALLIDO"

    def stopTest(self, test):
        self.actual["segundos"] = monotonic() - self.inicio
        self.evidencia.append(self.actual)
        super().stopTest(test)


class RunnerAislado(DiscoverRunner):
    def get_resultclass(self):
        return ResultadoConEvidencia

    def run_suite(self, suite, **kwargs):
        resultado = super().run_suite(suite, **kwargs)
        ruta = os.environ.get("CLOUDVAULT_RESULTADOS_FASE8")
        if ruta:
            Path(ruta).write_text(json.dumps(resultado.evidencia))
        return resultado

    def setup_databases(self, **kwargs):
        # El controlador instaló el SQL literal. Nunca crea, borra ni migra una
        # base externa. Verificar la propiedad del servidor antes de los tests.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, current_setting('data_directory')")
            base, usuario, datos = cursor.fetchone()
        esperado = Path(os.environ["CLOUDVAULT_FASE2_TMP"]) / "datos"
        if base != "test_cloudvault_fase2" or usuario != "cloudvault_pruebas" or Path(datos) != esperado:
            raise RuntimeError("Servidor ajeno al clúster desechable")
        return None

    def teardown_databases(self, old_config, **kwargs):
        connections.close_all()
