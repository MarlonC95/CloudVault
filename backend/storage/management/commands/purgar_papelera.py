"""Barrido acotado de papelera; simulación predeterminada y sin scheduler."""

import json
from datetime import timedelta
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.s3 import ClienteS3
from storage.papelera import ErrorPapelera, ServicioPapelera
from storage.repositorio_papelera import RepositorioPapelera


class Command(BaseCommand):
    help = "Selecciona o purga recursos vencidos y recupera intenciones incompletas."

    def add_arguments(self, parser):
        parser.add_argument("--ejecutar", action="store_true",
                            help="Confirma purgas físicas. Sin esta opción solo simula.")
        parser.add_argument("--limite", type=int, default=100,
                            help="Máximo total de recursos del barrido (1 a 100; predeterminado 100).")
        parser.add_argument("--organizacion-id", default=None,
                            help="Acota el barrido a una organización.")

    def handle(self, *args, **opciones):
        limite = opciones["limite"]
        if type(limite) is not int or not 1 <= limite <= 100:
            raise CommandError("--limite debe estar entre 1 y 100.")
        try:
            org = UUID(opciones["organizacion_id"]) if opciones["organizacion_id"] else None
        except (ValueError, TypeError, AttributeError):
            raise CommandError("--organizacion-id debe ser un UUID válido.") from None

        ahora = timezone.now()
        if timezone.is_naive(ahora):
            raise CommandError("El reloj del servidor no tiene zona horaria.")
        corte = ahora - timedelta(days=30)
        repo = RepositorioPapelera()
        try:
            candidatos = repo.seleccionar_candidatos_purga(
                corte=corte, ahora=ahora, limite=limite, organizacion_id=org)
        except Exception:
            raise CommandError("No fue posible seleccionar candidatos para la papelera.") from None

        resumen = {
            "modo": "ejecucion" if opciones["ejecutar"] else "simulacion",
            "instante_utc": ahora.isoformat(),
            "corte_inclusivo_utc": corte.isoformat(),
            "limite": limite,
            "candidatos_nuevos": sum(not c.es_recuperacion for c in candidatos),
            "recuperaciones": sum(c.es_recuperacion for c in candidatos),
            "completados": 0,
            "omitidos": 0,
            "ocupados": 0,
            "reintentables": 0,
            "diferidos": 0,
            "incompatibles": (getattr(repo, "incompatibles_ultima_seleccion", 0)
                              if type(getattr(repo, "incompatibles_ultima_seleccion", 0)) is int else 0),
            "bytes_fisicos_purgados": 0,
            "cuota_liberada_bytes": 0,
            "carpetas_vacias_purgadas": 0,
            "carpetas_vacias_candidatas": 0,
        }

        if not opciones["ejecutar"]:
            if type(repo) is RepositorioPapelera:
                try:
                    resumen["carpetas_vacias_candidatas"] = repo.purgar_carpetas_vacias_vencidas(
                        corte=corte, limite=max(0, limite - len(candidatos)),
                        organizacion_id=org, simular=True)
                except Exception:
                    raise CommandError("No fue posible seleccionar contenedores vencidos.") from None
            self.stdout.write(json.dumps(resumen, ensure_ascii=False, sort_keys=True))
            return None

        servicio = ServicioPapelera(repositorio=repo, reloj=lambda: ahora)
        for candidato in candidatos:
            try:
                bytes_eliminados = servicio.purgar_automaticamente(
                    candidato=candidato,
                    crear_cliente=lambda: ClienteS3(ConfiguracionS3.desde_entorno()),
                )
                resumen["completados"] += 1
                if type(bytes_eliminados) is int and bytes_eliminados >= 0:
                    resumen["bytes_fisicos_purgados"] += bytes_eliminados
                else:
                    resumen["reintentables"] += 1
            except ErrorPapelera as exc:
                if getattr(exc, "es_reclamo_ocupado", False) or exc.codigo == "RESOURCE_BUSY":
                    resumen["ocupados"] += 1
                elif exc.codigo == "CANDIDATE_STALE":
                    resumen["omitidos"] += 1
                elif exc.codigo == "RETRY_DEFERRED":
                    resumen["diferidos"] += 1
                elif exc.codigo == "PURGE_INCOMPATIBLE":
                    resumen["incompatibles"] += 1
                else:
                    resumen["reintentables"] += 1
            except Exception:
                resumen["reintentables"] += 1

        if type(repo) is RepositorioPapelera:
            try:
                carpetas = repo.purgar_carpetas_vacias_vencidas(
                    corte=corte, limite=max(0, limite - len(candidatos)),
                    organizacion_id=org, simular=not opciones["ejecutar"])
                if opciones["ejecutar"]:
                    resumen["carpetas_vacias_purgadas"] = carpetas
                else:
                    resumen["carpetas_vacias_candidatas"] = carpetas
            except Exception:
                resumen["reintentables"] += 1

        self.stdout.write(json.dumps(resumen, ensure_ascii=False, sort_keys=True))
        if (resumen["ocupados"] or resumen["reintentables"] or resumen["diferidos"]
                or resumen["incompatibles"]):
            raise CommandError("El barrido terminó con recursos pendientes; revise el resumen técnico.")
        return None
