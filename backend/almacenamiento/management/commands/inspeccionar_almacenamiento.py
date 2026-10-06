import json
from dataclasses import asdict

from django.core.management.base import BaseCommand, CommandError

from almacenamiento.esquema import inspeccionar_esquema


class Command(BaseCommand):
    help = "Revisar mapping técnico y advertencias sin modificar la base"

    def handle(self, *args, **options):
        informe = inspeccionar_esquema()
        self.stdout.write(json.dumps({"compatible": informe.compatible, **asdict(informe)}, ensure_ascii=False, indent=2))
        if not informe.compatible:
            raise CommandError("Esquema técnico incompatible; revisar con el responsable SQL")
