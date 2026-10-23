"""Comprueba el contrato del proveedor antes de activar la integración."""

import json

from django.core.management.base import BaseCommand, CommandError

from almacenamiento.conexion_negocio import PARAMETROS_PROVEEDOR, crear_servicios_almacenamiento
from almacenamiento.errores import ErrorCarga


class Command(BaseCommand):
    help = "Validar la fábrica de negocio y su interfaz sin invocar sus operaciones"

    def handle(self, *args, **options):
        informe = {"interfaz_compatible": False, "integracion_real_verificada": False,
                   "operaciones_requeridas": list(PARAMETROS_PROVEEDOR)}
        try:
            crear_servicios_almacenamiento()
        except ErrorCarga:
            self.stdout.write(json.dumps(informe, ensure_ascii=False))
            raise CommandError("Proveedor de negocio ausente o incompatible; revisar con su responsable.") from None
        informe["interfaz_compatible"] = True
        self.stdout.write(json.dumps(informe, ensure_ascii=False))
