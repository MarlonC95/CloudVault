"""Alternativa periódica sin broker; las tareas viven en PostgreSQL."""

import json
import time
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from almacenamiento.configuracion_inicio import entero_configurado
from almacenamiento.configuracion_mantenimiento import crear_servicio_mantenimiento


class Command(BaseCommand):
    help = "Vencer, reconciliar y limpiar cargas técnicas con seguimiento durable"

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true")
        parser.add_argument("--intervalo", type=int)
        parser.add_argument("--ciclos", type=int, help="Limita ejecuciones del proceso periódico")

    def handle(self, *args, **options):
        try:
            intervalo = options["intervalo"]
            if intervalo is None:
                intervalo = entero_configurado("ALMACENAMIENTO_MANTENIMIENTO_INTERVALO", 60)
            ciclos = options["ciclos"]
            if not 0 < intervalo <= 3600 or (ciclos is not None and ciclos <= 0):
                raise ValueError("Parámetros inválidos")
            if ciclos is not None and not options["continuo"]:
                raise ValueError("Ciclos requiere modo periódico")
            servicio = crear_servicio_mantenimiento()
        except Exception:
            raise CommandError("Configuración de mantenimiento inválida.") from None
        ejecutados = 0
        try:
            while True:
                inicio = time.monotonic()
                fecha = datetime.now(timezone.utc).isoformat()
                fallo = False
                try:
                    informe = servicio.ejecutar()
                except Exception:
                    # No serializar mensajes SQL/SDK, claves ni credenciales.
                    informe = {"error": "SERVICE_UNAVAILABLE"}
                    fallo = True
                incidencias = {"SQL", "S3", "DEPENDENCIA", "INTEGRIDAD", "ERROR",
                               "COPY_AMBIGUO", "RECUPERACION"}
                nivel = ("error" if fallo else "warn" if incidencias.intersection(
                    informe.get("resultados", {})) else "info")
                self.stdout.write(json.dumps({"evento": "mantenimiento_ciclo", "level": nivel,
                                              "message": "Mantenimiento no disponible." if fallo else
                                                         "Ciclo de mantenimiento completado.",
                                              "fecha_utc": fecha,
                                              "duracion_segundos": round(time.monotonic() - inicio, 3),
                                              "ciclo": ejecutados + 1, "intervalo_segundos": intervalo,
                                              **informe}, ensure_ascii=False))
                self.stdout.flush()
                if fallo and not options["continuo"]:
                    raise CommandError("Mantenimiento no disponible; revisar dependencias.") from None
                ejecutados += 1
                if not options["continuo"] or (ciclos is not None and ejecutados >= ciclos):
                    break
                time.sleep(max(0, intervalo - (time.monotonic() - inicio)))
        except KeyboardInterrupt:
            self.stdout.write("Mantenimiento detenido; el trabajo pendiente permanece en PostgreSQL.")
