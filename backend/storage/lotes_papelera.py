"""Operaciones lógicas acotadas de carpeta sobre el esquema existente."""

from contextlib import ExitStack
from datetime import datetime, timedelta
from functools import wraps
from math import ceil
from types import SimpleNamespace
from unicodedata import normalize
from uuid import UUID, uuid4

from django.utils import timezone
from django.db import DatabaseError
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Archivo, Carpeta
from .papelera import ErrorPapelera, identificador
from .permisos_papelera import autorizar_envio
from .repositorio_papelera import RepositorioPapelera
from auth_workspaces.models import LogAuditoria


LIMITE_LOTE_CARPETA = 100


def _error_limite():
    return ErrorPapelera("VALIDATION_ERROR", 409,
                         fields={"limite": ["La operación admite hasta 100 elementos."]})


def _controlar_base_datos(metodo):
    @wraps(metodo)
    def ejecutar(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except DatabaseError:
            raise ErrorPapelera() from None
    return ejecutar


class ServicioLotesCarpeta:
    """Envía/restaura árboles síncronos; las transiciones usan auditoría JSON."""

    def __init__(self, *, repo=None, reloj=timezone.now, nuevo_id=uuid4):
        self.repo = repo or RepositorioPapelera()
        self.reloj = reloj
        self.nuevo_id = nuevo_id

    def _arbol(self, raiz_id, org):
        raiz = Carpeta.objects.using(self.repo.using).filter(
            pk=raiz_id, organizacion_id=org).first()
        if raiz is None:
            raise NotFound()
        carpetas, archivos, pendientes = {}, {}, [raiz_id]
        while pendientes:
            pagina = list(Carpeta.objects.using(self.repo.using).filter(
                padre_id__in=pendientes).order_by("id")[:LIMITE_LOTE_CARPETA + 1])
            if len(pagina) > LIMITE_LOTE_CARPETA:
                raise _error_limite()
            pendientes = []
            for carpeta in pagina:
                if carpeta.pk in carpetas or carpeta.pk == raiz_id:
                    raise ErrorPapelera("VALIDATION_ERROR", 409)
                if carpeta.organizacion_id != org:
                    raise ErrorPapelera("VALIDATION_ERROR", 409)
                carpetas[carpeta.pk] = carpeta
                pendientes.append(carpeta.pk)
                if len(carpetas) > LIMITE_LOTE_CARPETA:
                    raise _error_limite()
            if pendientes:
                filas = Archivo.objects.using(self.repo.using).filter(
                    carpeta_id__in=pendientes).order_by("id")[:LIMITE_LOTE_CARPETA + 1]
                if len(filas) > LIMITE_LOTE_CARPETA:
                    raise _error_limite()
                for archivo in filas:
                    if archivo.organizacion_id != org:
                        raise ErrorPapelera("VALIDATION_ERROR", 409)
                    archivos[archivo.pk] = archivo
                    if len(carpetas) + len(archivos) > LIMITE_LOTE_CARPETA:
                        raise _error_limite()
        carpetas[raiz.pk] = raiz
        # Detecta referencias de archivo de organización ajena en cualquier nivel.
        if carpetas:
            filas = Archivo.objects.using(self.repo.using).filter(
                carpeta_id__in=carpetas).order_by("id")[:LIMITE_LOTE_CARPETA + 1]
            if len(filas) > LIMITE_LOTE_CARPETA:
                raise _error_limite()
            for archivo in filas:
                if archivo.organizacion_id != org:
                    raise ErrorPapelera("VALIDATION_ERROR", 409)
                archivos[archivo.pk] = archivo
        if len(carpetas) + len(archivos) > LIMITE_LOTE_CARPETA:
            raise _error_limite()
        return raiz, carpetas, archivos

    @_controlar_base_datos
    def enviar(self, *, solicitante_id, organizacion_id, carpeta_id):
        actor, org, raiz_id = map(identificador,
                                  (solicitante_id, organizacion_id, carpeta_id))
        _, snapshot_carpetas, snapshot_archivos = self._arbol(raiz_id, org)
        ids_archivo = sorted(snapshot_archivos, key=str)
        with ExitStack() as reclamos:
            comprobaciones = []
            for archivo_id in ids_archivo:
                comprobaciones.append(reclamos.enter_context(self.repo.reclamar(archivo_id)))
            with self.repo.transaccion(org):
                for comprobar in comprobaciones:
                    comprobar()
                nivel = self.repo.nivel(actor, org)
                raiz, carpetas, archivos = self._arbol(raiz_id, org)
                if (set(carpetas) != set(snapshot_carpetas)
                        or set(archivos) != set(snapshot_archivos)):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                if raiz.en_papelera:
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                if nivel == 3:
                    recurso = SimpleNamespace(pk=None, carpeta_id=raiz.pk,
                                              organizacion_id=org)
                    autorizar_envio(nivel, self.repo.permisos(actor, recurso))
                elif nivel != 0:
                    raise PermissionDenied()
                activos_carpetas = [c for c in carpetas.values() if not c.en_papelera]
                activos_archivos = [a for a in archivos.values() if not a.en_papelera]
                if nivel == 3:
                    for carpeta in activos_carpetas:
                        autorizar_envio(nivel, self.repo.permisos(actor, SimpleNamespace(
                            pk=None, carpeta_id=carpeta.pk, organizacion_id=org)))
                    for archivo in activos_archivos:
                        autorizar_envio(nivel, self.repo.permisos(actor, archivo))
                # No crear una operación nueva alrededor de un descendiente eliminado.
                for carpeta in carpetas.values():
                    if carpeta.en_papelera and any(
                            not c.en_papelera and self._es_descendiente(c, carpeta, carpetas)
                            for c in carpetas.values()):
                        raise ErrorPapelera("VALIDATION_ERROR", 409)
                for archivo in activos_archivos:
                    if self.repo.purga_pendiente(archivo):
                        raise ErrorPapelera("RESOURCE_BUSY", 409)
                ahora = self.reloj()
                if timezone.is_naive(ahora):
                    raise ErrorPapelera()
                operacion = str(self.nuevo_id())
                miembros = []
                generaciones = {}
                for carpeta in sorted(activos_carpetas, key=lambda c: str(c.pk)):
                    generacion = str(self.nuevo_id())
                    generaciones[("carpeta", str(carpeta.pk))] = generacion
                    miembros.append({"tipo_elemento": "carpeta", "recurso_id": str(carpeta.pk),
                                     "generacion_id": generacion,
                                     "padre_id": str(carpeta.padre_id) if carpeta.padre_id else None,
                                     "nombre": carpeta.nombre})
                for archivo in sorted(activos_archivos, key=lambda a: str(a.pk)):
                    generacion = str(self.nuevo_id())
                    generaciones[("archivo", str(archivo.pk))] = generacion
                    miembros.append({"tipo_elemento": "archivo", "recurso_id": str(archivo.pk),
                                     "generacion_id": generacion,
                                     "padre_id": str(archivo.carpeta_id) if archivo.carpeta_id else None,
                                     "nombre": archivo.nombre, "tamano_bytes": archivo.tamano_bytes})
                if not miembros:
                    raise ErrorPapelera("VALIDATION_ERROR", 409)
                for carpeta in activos_carpetas:
                    carpeta.en_papelera, carpeta.fecha_papelera = True, ahora
                    carpeta.save(using=self.repo.using,
                                 update_fields=["en_papelera", "fecha_papelera"])
                for archivo in activos_archivos:
                    archivo.en_papelera, archivo.fecha_papelera = True, ahora
                    archivo.save(using=self.repo.using,
                                 update_fields=["en_papelera", "fecha_papelera", "actualizado_en"])
                    self.repo.auditar(archivo=archivo, actor=actor, detalles={
                        "version": 1, "operacion_id": operacion,
                        "generacion_id": generaciones[("archivo", str(archivo.pk))],
                        "tipo_elemento": "archivo", "recurso_id": str(archivo.pk),
                        "fecha_papelera": ahora.isoformat(), "origen": "CARPETA",
                        "tamano_bytes": archivo.tamano_bytes,
                        "carpeta_original_id": str(archivo.carpeta_id) if archivo.carpeta_id else None,
                    })
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_CARPETA_ENVIADA", detalles={
                        "version": 1, "operacion_id": operacion,
                        "tipo_elemento": "carpeta", "raiz_id": str(raiz.pk),
                        "raiz_generacion_id": generaciones[("carpeta", str(raiz.pk))],
                        "actor_id": str(actor), "fecha_papelera": ahora.isoformat(),
                        "miembros": miembros, "cerrado": True,
                    })

    @_controlar_base_datos
    def purgar(self, *, solicitante_id, organizacion_id, carpeta_id, crear_cliente):
        """Fija una selección durable antes de S3 y la reanuda sin ampliarla."""
        from .papelera import ServicioPapelera

        actor, org, raiz_id = map(identificador,
                                  (solicitante_id, organizacion_id, carpeta_id))
        pendiente = LogAuditoria.objects.using(self.repo.using).filter(
            organizacion_id=org, accion="PAPELERA_CARPETA_PURGA_SOLICITADA",
            detalles__version=1, detalles__raiz_id=str(raiz_id),
        ).order_by("-id").first()
        seleccion = pendiente.detalles if pendiente else None
        if isinstance(seleccion, dict) and seleccion and LogAuditoria.objects.using(self.repo.using).filter(
                organizacion_id=org, accion="PAPELERA_CARPETA_PURGADA",
                detalles__version=1,
                detalles__operacion_id=seleccion.get("operacion_id")).exists():
            raise NotFound()
        if seleccion is not None and (
                not isinstance(seleccion, dict) or seleccion.get("version") != 1
                or seleccion.get("raiz_id") != str(raiz_id)
                or not isinstance(seleccion.get("miembros"), list)
                or len(seleccion["miembros"]) > LIMITE_LOTE_CARPETA
                or not seleccion.get("operacion_id")):
            raise ErrorPapelera()
        if isinstance(seleccion, dict):
            self._validar_miembros_seleccion(seleccion["miembros"])
        if not isinstance(seleccion, dict):
            _, snapshot_carpetas, snapshot_archivos = self._arbol(raiz_id, org)
            if any(not c.en_papelera for c in snapshot_carpetas.values()) or any(
                    not a.en_papelera for a in snapshot_archivos.values()):
                raise ErrorPapelera("VALIDATION_ERROR", 409)
            miembros = []
            for carpeta in sorted(snapshot_carpetas.values(), key=lambda c: str(c.pk)):
                if carpeta.fecha_papelera is None or timezone.is_naive(carpeta.fecha_papelera):
                    raise ErrorPapelera()
                manifiesto, detalles, miembro = self._manifiesto_miembro_carpeta(carpeta.pk, org)
                if (miembro is None or not miembro.get("generacion_id")
                        or detalles.get("fecha_papelera") != carpeta.fecha_papelera.isoformat()):
                    raise ErrorPapelera()
                miembros.append({"tipo_elemento": "carpeta", "recurso_id": str(carpeta.pk),
                                 "generacion_id": miembro["generacion_id"],
                                 "manifiesto_operacion_id": detalles.get("operacion_id"),
                                 "fecha_papelera": carpeta.fecha_papelera.isoformat()})
            for archivo in sorted(snapshot_archivos.values(), key=lambda a: str(a.pk)):
                if archivo.fecha_papelera is None or timezone.is_naive(archivo.fecha_papelera):
                    raise ErrorPapelera()
                ultimo = self.repo.ultimo_evento(archivo)
                if ultimo is None or not ultimo.detalles.get("generacion_id"):
                    raise ErrorPapelera()
                miembros.append({"tipo_elemento": "archivo", "recurso_id": str(archivo.pk),
                                 "generacion_id": ultimo.detalles["generacion_id"],
                                 "fecha_papelera": archivo.fecha_papelera.isoformat()})
            if len(miembros) > LIMITE_LOTE_CARPETA:
                raise _error_limite()
            if any(self.repo.lote_purga_pendiente(org, miembro["recurso_id"])
                   for miembro in miembros):
                raise ErrorPapelera("RESOURCE_BUSY", 409)
            with self.repo.transaccion(org):
                if self.repo.nivel(actor, org) != 0:
                    raise PermissionDenied()
                raiz = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                    pk=raiz_id, organizacion_id=org, en_papelera=True).first()
                if raiz is None:
                    raise NotFound()
                _, carpetas_actuales, archivos_actuales = self._arbol(raiz_id, org)
                if (set(carpetas_actuales) != set(snapshot_carpetas)
                        or set(archivos_actuales) != set(snapshot_archivos)):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                if any(self.repo.lote_purga_pendiente(org, miembro["recurso_id"])
                       for miembro in miembros):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                for miembro in miembros:
                    rid = UUID(miembro["recurso_id"])
                    if miembro["tipo_elemento"] == "archivo":
                        fila = Archivo.objects.using(self.repo.using).select_for_update().filter(
                            pk=rid, organizacion_id=org, en_papelera=True).first()
                        ultimo = self.repo.ultimo_evento(fila) if fila else None
                    else:
                        fila = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                            pk=rid, organizacion_id=org, en_papelera=True).first()
                        _, detalles_actuales, miembro_actual = self._manifiesto_miembro_carpeta(rid, org)
                        valido = bool(
                            miembro_actual
                            and detalles_actuales.get("operacion_id") == miembro.get("manifiesto_operacion_id")
                            and miembro_actual.get("generacion_id") == miembro.get("generacion_id")
                            and fila is not None
                            and fila.fecha_papelera.isoformat() == miembro.get("fecha_papelera")
                        )
                        if not valido:
                            raise ErrorPapelera("CANDIDATE_STALE", 409)
                        ultimo = None
                    if fila is None or (
                            miembro["tipo_elemento"] == "archivo"
                            and (ultimo is None
                                 or ultimo.detalles.get("generacion_id") != miembro["generacion_id"]
                                 or fila.fecha_papelera.isoformat() != miembro.get("fecha_papelera"))):
                        raise ErrorPapelera("CANDIDATE_STALE", 409)
                operacion = str(self.nuevo_id())
                seleccion = {"version": 1, "operacion_id": operacion,
                             "tipo_elemento": "carpeta", "raiz_id": str(raiz_id),
                             "actor_id": str(actor), "iniciada_en": self.reloj().isoformat(),
                             "miembros": miembros}
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_CARPETA_PURGA_SOLICITADA", detalles=seleccion)

        errores = 0
        servicio = ServicioPapelera()
        for miembro in seleccion.get("miembros", []):
            if not isinstance(miembro, dict) or miembro.get("tipo_elemento") != "archivo":
                continue
            rid = UUID(miembro["recurso_id"])
            fila = Archivo.objects.using(self.repo.using).filter(
                pk=rid, organizacion_id=org).first()
            if fila is None:
                cerrada = LogAuditoria.objects.using(self.repo.using).filter(
                    organizacion_id=org, accion="PAPELERA_PURGADO",
                    detalles__version=1,
                    detalles__tipo_elemento="archivo",
                    detalles__recurso_id=str(rid),
                    detalles__generacion_id=miembro["generacion_id"],
                    detalles__fecha_papelera=miembro.get("fecha_papelera"),
                ).exists()
                if cerrada:
                    continue
                errores += 1
                continue
            ultimo = self.repo.ultimo_evento(fila)
            if (ultimo is None or ultimo.detalles.get("generacion_id") != miembro["generacion_id"]
                    or fila.fecha_papelera is None
                    or fila.fecha_papelera.isoformat() != miembro.get("fecha_papelera")):
                errores += 1
                continue
            try:
                servicio.purgar(solicitante_id=actor, organizacion_id=org,
                                archivo_id=rid,
                                crear_cliente=crear_cliente,
                                operacion_lote_id=seleccion["operacion_id"])
            except Exception:
                errores += 1
        if errores:
            raise ErrorPapelera("SERVICE_UNAVAILABLE", 503)
        with self.repo.transaccion(org):
            if self.repo.nivel(actor, org) != 0:
                raise PermissionDenied()
            ids_carpetas = [UUID(m["recurso_id"]) for m in seleccion["miembros"]
                            if m.get("tipo_elemento") == "carpeta"]
            profundidad = {}
            for carpeta_id in ids_carpetas:
                actual, nivel, visitados = carpeta_id, 0, set()
                while actual is not None and actual not in visitados:
                    visitados.add(actual)
                    fila = Carpeta.objects.using(self.repo.using).filter(
                        pk=actual, organizacion_id=org).first()
                    if fila is None:
                        break
                    actual, nivel = fila.padre_id, nivel + 1
                if actual is not None:
                    raise ErrorPapelera("VALIDATION_ERROR", 409)
                profundidad[carpeta_id] = nivel
            for carpeta_id in sorted(ids_carpetas, key=lambda i: (-profundidad[i], str(i))):
                miembro = next(m for m in seleccion["miembros"]
                               if m.get("tipo_elemento") == "carpeta"
                               and m.get("recurso_id") == str(carpeta_id))
                carpeta = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                    pk=carpeta_id, organizacion_id=org, en_papelera=True).first()
                if carpeta is None:
                    raise ErrorPapelera("CANDIDATE_STALE", 409)
                _, detalles_actuales, miembro_actual = self._manifiesto_miembro_carpeta(carpeta_id, org)
                if (miembro_actual is None
                        or detalles_actuales.get("operacion_id") != miembro.get("manifiesto_operacion_id")
                        or miembro_actual.get("generacion_id") != miembro.get("generacion_id")
                        or carpeta.fecha_papelera.isoformat() != miembro.get("fecha_papelera")):
                    raise ErrorPapelera("CANDIDATE_STALE", 409)
                if (Archivo.objects.using(self.repo.using).filter(carpeta_id=carpeta_id).exists()
                        or Carpeta.objects.using(self.repo.using).filter(padre_id=carpeta_id).exists()):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                carpeta.delete(using=self.repo.using)
            LogAuditoria.objects.using(self.repo.using).create(
                usuario_id=actor, organizacion_id=org,
                accion="PAPELERA_CARPETA_PURGADA", detalles={
                    "version": 1, "operacion_id": seleccion["operacion_id"],
                    "raiz_id": str(raiz_id),
                    "miembros": seleccion["miembros"], "cerrado": True,
                })

    @_controlar_base_datos
    def vaciar(self, *, solicitante_id, organizacion_id, crear_cliente, operacion_id=None):
        """Fija/reanuda una selección del propietario sin volver a consultar la papelera."""
        from .papelera import ServicioPapelera

        actor, org = map(identificador, (solicitante_id, organizacion_id))
        if operacion_id is None:
            for previa in LogAuditoria.objects.using(self.repo.using).filter(
                    organizacion_id=org, accion="PAPELERA_VACIADO_INICIADO",
                    detalles__version=1).order_by("-id")[:100]:
                d = previa.detalles
                if not isinstance(d, dict) or not d.get("operacion_id"):
                    continue
                if not LogAuditoria.objects.using(self.repo.using).filter(
                        organizacion_id=org, accion="PAPELERA_VACIADO_CERRADO",
                        detalles__version=1,
                        detalles__operacion_id=d["operacion_id"]).exists():
                    operacion_id = d["operacion_id"]
                    break
        if operacion_id is None:
            with self.repo.transaccion(org):
                if self.repo.nivel(actor, org) != 0:
                    raise PermissionDenied()
                anteriores = LogAuditoria.objects.using(self.repo.using).filter(
                    organizacion_id=org, accion="PAPELERA_VACIADO_INICIADO",
                    detalles__version=1).order_by("-id")[:100]
                for previa in anteriores:
                    d = previa.detalles
                    if (isinstance(d, dict) and d.get("operacion_id")
                            and not LogAuditoria.objects.using(self.repo.using).filter(
                                organizacion_id=org, accion="PAPELERA_VACIADO_CERRADO",
                                detalles__version=1,
                                detalles__operacion_id=d["operacion_id"]).exists()):
                        raise ErrorPapelera("RESOURCE_BUSY", 409,
                                            fields={"operacion_id": [d["operacion_id"]]})
                archivos = list(Archivo.objects.using(self.repo.using).select_for_update().filter(
                    organizacion_id=org, en_papelera=True).order_by("id")[:LIMITE_LOTE_CARPETA + 1])
                if len(archivos) > LIMITE_LOTE_CARPETA:
                    raise _error_limite()
                carpetas = list(Carpeta.objects.using(self.repo.using).select_for_update().filter(
                    organizacion_id=org, en_papelera=True).order_by("id")[:LIMITE_LOTE_CARPETA + 1])
                if len(carpetas) > LIMITE_LOTE_CARPETA:
                    raise _error_limite()
                miembros = []
                for archivo in archivos:
                    if archivo.fecha_papelera is None or timezone.is_naive(archivo.fecha_papelera):
                        raise ErrorPapelera()
                    ultimo = self.repo.ultimo_evento(archivo)
                    if ultimo is None:
                        raise ErrorPapelera()
                    miembros.append({"tipo_elemento": "archivo", "recurso_id": str(archivo.pk),
                                     "generacion_id": ultimo.detalles["generacion_id"],
                                     "fecha_papelera": archivo.fecha_papelera.isoformat()})
                for carpeta in carpetas:
                    if carpeta.fecha_papelera is None or timezone.is_naive(carpeta.fecha_papelera):
                        raise ErrorPapelera()
                    _, d, miembro = self._manifiesto_miembro_carpeta(carpeta.pk, org)
                    if (miembro is None or d.get("fecha_papelera") != carpeta.fecha_papelera.isoformat()):
                        raise ErrorPapelera()
                    miembros.append({"tipo_elemento": "carpeta", "recurso_id": str(carpeta.pk),
                                     "generacion_id": miembro["generacion_id"],
                                     "manifiesto_operacion_id": d["operacion_id"],
                                     "fecha_papelera": carpeta.fecha_papelera.isoformat()})
                if len(miembros) > LIMITE_LOTE_CARPETA:
                    raise _error_limite()
                if any(self.repo.lote_purga_pendiente(org, miembro["recurso_id"])
                       for miembro in miembros):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                operacion = str(self.nuevo_id())
                seleccion = {"version": 1, "operacion_id": operacion,
                             "tipo_elemento": "vaciado", "actor_id": str(actor),
                             "iniciada_en": self.reloj().isoformat(), "miembros": miembros}
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_VACIADO_INICIADO", detalles=seleccion)
        else:
            operacion = str(identificador(operacion_id))
            evento = LogAuditoria.objects.using(self.repo.using).filter(
                organizacion_id=org, accion="PAPELERA_VACIADO_INICIADO",
                detalles__version=1, detalles__operacion_id=operacion,
            ).first()
            seleccion = evento.detalles if evento else None
            if (not isinstance(seleccion, dict) or seleccion.get("version") != 1
                    or not isinstance(seleccion.get("miembros"), list)
                    or len(seleccion["miembros"]) > LIMITE_LOTE_CARPETA):
                raise NotFound()
            self._validar_miembros_seleccion(seleccion["miembros"])
            with self.repo.transaccion(org):
                if self.repo.nivel(actor, org) != 0:
                    raise PermissionDenied()
        if LogAuditoria.objects.using(self.repo.using).filter(
                organizacion_id=org, accion="PAPELERA_VACIADO_CERRADO",
                detalles__version=1, detalles__operacion_id=seleccion["operacion_id"]).exists():
            return seleccion["operacion_id"]

        errores = 0
        servicio = ServicioPapelera()
        for miembro in seleccion.get("miembros", []):
            if not isinstance(miembro, dict) or miembro.get("tipo_elemento") != "archivo":
                continue
            try:
                rid = UUID(miembro["recurso_id"])
            except (KeyError, ValueError, TypeError):
                errores += 1
                continue
            fila = Archivo.objects.using(self.repo.using).filter(
                pk=rid, organizacion_id=org).first()
            if fila is None:
                if LogAuditoria.objects.using(self.repo.using).filter(
                        organizacion_id=org, accion="PAPELERA_PURGADO",
                        detalles__version=1, detalles__tipo_elemento="archivo",
                        detalles__recurso_id=str(rid),
                        detalles__generacion_id=miembro.get("generacion_id"),
                        detalles__fecha_papelera=miembro.get("fecha_papelera")).exists():
                    continue
                errores += 1
                continue
            ultimo = self.repo.ultimo_evento(fila)
            if (not fila.en_papelera or ultimo is None
                    or ultimo.detalles.get("generacion_id") != miembro.get("generacion_id")
                    or fila.fecha_papelera is None
                    or fila.fecha_papelera.isoformat() != miembro.get("fecha_papelera")):
                errores += 1
                continue
            try:
                servicio.purgar(solicitante_id=actor, organizacion_id=org,
                                archivo_id=rid, crear_cliente=crear_cliente,
                                operacion_lote_id=seleccion["operacion_id"])
            except Exception:
                errores += 1

        with self.repo.transaccion(org):
            if self.repo.nivel(actor, org) != 0:
                raise PermissionDenied()
            ids_carpetas = []
            for miembro in seleccion.get("miembros", []):
                if miembro.get("tipo_elemento") != "carpeta":
                    continue
                try:
                    ids_carpetas.append(UUID(miembro["recurso_id"]))
                except (KeyError, ValueError, TypeError):
                    errores += 1
            profundidad = {}
            for carpeta_id in ids_carpetas:
                actual, nivel, visitados = carpeta_id, 0, set()
                while actual is not None and actual not in visitados:
                    visitados.add(actual)
                    fila = Carpeta.objects.using(self.repo.using).filter(
                        pk=actual, organizacion_id=org).first()
                    if fila is None:
                        break
                    actual, nivel = fila.padre_id, nivel + 1
                if actual is not None:
                    errores += 1
                profundidad[carpeta_id] = nivel
            for carpeta_id in sorted(ids_carpetas, key=lambda i: (-profundidad.get(i, 0), str(i))):
                miembro = next(m for m in seleccion["miembros"]
                               if m.get("tipo_elemento") == "carpeta"
                               and m.get("recurso_id") == str(carpeta_id))
                carpeta = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                    pk=carpeta_id, organizacion_id=org, en_papelera=True).first()
                if carpeta is None:
                    # Puede haberse completado una parte en una ejecución previa.
                    if LogAuditoria.objects.using(self.repo.using).filter(
                            organizacion_id=org, accion="PAPELERA_VACIADO_RECURSO_PURGADO",
                            detalles__operacion_id=seleccion["operacion_id"],
                            detalles__recurso_id=str(carpeta_id)).exists():
                        continue
                    errores += 1
                    continue
                _, detalles_actuales, miembro_actual = self._manifiesto_miembro_carpeta(carpeta_id, org)
                if (miembro_actual is None
                        or detalles_actuales.get("operacion_id") != miembro.get("manifiesto_operacion_id")
                        or miembro_actual.get("generacion_id") != miembro.get("generacion_id")
                        or carpeta.fecha_papelera is None
                        or carpeta.fecha_papelera.isoformat() != miembro.get("fecha_papelera")):
                    errores += 1
                    continue
                if (Archivo.objects.using(self.repo.using).filter(carpeta_id=carpeta_id).exists()
                        or Carpeta.objects.using(self.repo.using).filter(padre_id=carpeta_id).exists()):
                    errores += 1
                    continue
                carpeta.delete(using=self.repo.using)
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_VACIADO_RECURSO_PURGADO", detalles={
                        "version": 1, "operacion_id": seleccion["operacion_id"],
                        "recurso_id": str(carpeta_id),
                    })
            if errores == 0:
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_VACIADO_CERRADO", detalles={
                        "version": 1, "operacion_id": seleccion["operacion_id"],
                        "miembros": seleccion["miembros"], "cerrado": True,
                    })
        if errores:
            raise ErrorPapelera("SERVICE_UNAVAILABLE", 503,
                                fields={"operacion_id": [seleccion["operacion_id"]]})
        return seleccion["operacion_id"]

    @_controlar_base_datos
    def estado_vaciado(self, *, solicitante_id, organizacion_id, operacion_id):
        actor, org, operacion = map(identificador,
                                    (solicitante_id, organizacion_id, operacion_id))
        with self.repo.transaccion(org):
            if self.repo.nivel(actor, org) != 0:
                raise PermissionDenied()
            evento = LogAuditoria.objects.using(self.repo.using).filter(
                organizacion_id=org, accion="PAPELERA_VACIADO_INICIADO",
                detalles__version=1, detalles__operacion_id=str(operacion),
            ).first()
            if evento is None or not isinstance(evento.detalles, dict):
                raise NotFound()
            miembros = evento.detalles.get("miembros")
            if not isinstance(miembros, list) or len(miembros) > LIMITE_LOTE_CARPETA:
                raise ErrorPapelera()
            self._validar_miembros_seleccion(miembros)
            completados, pendientes, obsoletos = 0, 0, 0
            for miembro in miembros:
                if not isinstance(miembro, dict):
                    raise ErrorPapelera()
                rid = UUID(miembro.get("recurso_id"))
                if miembro.get("tipo_elemento") == "archivo":
                    fila = Archivo.objects.using(self.repo.using).filter(
                        pk=rid, organizacion_id=org).first()
                    listo = (fila is None and LogAuditoria.objects.using(self.repo.using).filter(
                        organizacion_id=org, accion="PAPELERA_PURGADO",
                        detalles__version=1, detalles__recurso_id=str(rid),
                        detalles__generacion_id=miembro.get("generacion_id"),
                        detalles__fecha_papelera=miembro.get("fecha_papelera")).exists())
                    vigente = bool(fila and fila.en_papelera and
                                   self.repo.ultimo_evento(fila) and
                                   self.repo.ultimo_evento(fila).detalles.get("generacion_id")
                                   == miembro.get("generacion_id")
                                   and fila.fecha_papelera is not None
                                   and fila.fecha_papelera.isoformat() == miembro.get("fecha_papelera"))
                elif miembro.get("tipo_elemento") == "carpeta":
                    fila = Carpeta.objects.using(self.repo.using).filter(
                        pk=rid, organizacion_id=org).first()
                    listo = (fila is None and LogAuditoria.objects.using(self.repo.using).filter(
                        organizacion_id=org, accion="PAPELERA_VACIADO_RECURSO_PURGADO",
                        detalles__operacion_id=str(operacion),
                        detalles__recurso_id=str(rid)).exists())
                    _, detalles_actuales, miembro_actual = self._manifiesto_miembro_carpeta(rid, org)
                    vigente = bool(
                        fila and fila.en_papelera and miembro_actual
                        and detalles_actuales.get("operacion_id") == miembro.get("manifiesto_operacion_id")
                        and miembro_actual.get("generacion_id") == miembro.get("generacion_id")
                        and fila.fecha_papelera is not None
                        and fila.fecha_papelera.isoformat() == miembro.get("fecha_papelera"))
                else:
                    raise ErrorPapelera()
                completados += bool(listo)
                pendientes += bool(vigente and not listo)
                obsoletos += bool(not listo and not vigente)
            cerrado = LogAuditoria.objects.using(self.repo.using).filter(
                organizacion_id=org, accion="PAPELERA_VACIADO_CERRADO",
                detalles__version=1, detalles__operacion_id=str(operacion)).exists()
            return {"operacion_id": str(operacion),
                    "estado": "completado" if cerrado else "pendiente" if pendientes else "incompleto",
                    "total": len(miembros), "completados": completados,
                    "pendientes": pendientes, "obsoletos": obsoletos}

    @staticmethod
    def _es_descendiente(carpeta, ancestro, carpetas):
        padre, visitados = carpeta.padre_id, set()
        while padre is not None:
            if padre in visitados:
                raise ErrorPapelera("VALIDATION_ERROR", 409)
            visitados.add(padre)
            if padre == ancestro.pk:
                return True
            superior = carpetas.get(padre)
            if superior is None:
                break
            padre = superior.padre_id
        return False

    @staticmethod
    def _validar_miembros_seleccion(miembros):
        if not isinstance(miembros, list) or len(miembros) > LIMITE_LOTE_CARPETA:
            raise ErrorPapelera()
        identificadores = set()
        for miembro in miembros:
            if (not isinstance(miembro, dict)
                    or miembro.get("tipo_elemento") not in {"archivo", "carpeta"}
                    or not isinstance(miembro.get("generacion_id"), str)
                    or not miembro.get("generacion_id")
                    or not isinstance(miembro.get("fecha_papelera"), str)):
                raise ErrorPapelera()
            try:
                recurso_id = UUID(miembro["recurso_id"])
                fecha = datetime.fromisoformat(miembro["fecha_papelera"])
            except (KeyError, ValueError, TypeError):
                raise ErrorPapelera() from None
            if timezone.is_naive(fecha):
                raise ErrorPapelera()
            clave = (miembro["tipo_elemento"], recurso_id)
            if clave in identificadores:
                raise ErrorPapelera()
            identificadores.add(clave)
            if (miembro["tipo_elemento"] == "carpeta"
                    and (not isinstance(miembro.get("manifiesto_operacion_id"), str)
                         or not miembro.get("manifiesto_operacion_id"))):
                raise ErrorPapelera()

    def _manifiesto(self, raiz_id, org):
        evento = LogAuditoria.objects.using(self.repo.using).filter(
            organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
            detalles__version=1, detalles__raiz_id=str(raiz_id),
        ).order_by("-id").first()
        detalles = evento.detalles if evento else None
        if (not isinstance(detalles, dict) or detalles.get("cerrado") is not True
                or not isinstance(detalles.get("miembros"), list)
                or len(detalles["miembros"]) > LIMITE_LOTE_CARPETA):
            raise NotFound()
        identificadores, raiz = set(), None
        for miembro in detalles["miembros"]:
            if (not isinstance(miembro, dict)
                    or miembro.get("tipo_elemento") not in {"archivo", "carpeta"}
                    or not miembro.get("generacion_id")):
                raise ErrorPapelera()
            try:
                UUID(miembro["recurso_id"])
            except (KeyError, ValueError, TypeError):
                raise ErrorPapelera() from None
            clave = (miembro["tipo_elemento"], miembro["recurso_id"])
            if clave in identificadores:
                raise ErrorPapelera()
            identificadores.add(clave)
            if (miembro["tipo_elemento"] == "carpeta"
                    and miembro["recurso_id"] == str(raiz_id)):
                raiz = miembro
        if (raiz is None or raiz.get("generacion_id") != detalles.get("raiz_generacion_id")
                or not detalles.get("operacion_id")):
            raise ErrorPapelera()
        return evento, detalles

    def _manifiesto_miembro_carpeta(self, carpeta_id, org):
        evento = LogAuditoria.objects.using(self.repo.using).filter(
            organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
            detalles__version=1,
            detalles__miembros__contains=[{"recurso_id": str(carpeta_id)}],
        ).order_by("-id").first()
        detalles = evento.detalles if evento else None
        if not isinstance(detalles, dict) or detalles.get("cerrado") is not True:
            return evento, detalles, None
        miembro = next((m for m in detalles.get("miembros", [])
                        if isinstance(m, dict) and m.get("tipo_elemento") == "carpeta"
                        and m.get("recurso_id") == str(carpeta_id)), None)
        return evento, detalles, miembro

    @staticmethod
    def _manifiesto_sigue_vigente(inicial, actual):
        evento_inicial, datos_inicial = inicial
        evento_actual, datos_actual = actual
        return bool(evento_inicial.pk == evento_actual.pk
                    and datos_inicial.get("operacion_id") == datos_actual.get("operacion_id")
                    and datos_inicial.get("raiz_generacion_id")
                    == datos_actual.get("raiz_generacion_id"))

    @staticmethod
    def _generacion_carpeta_vigente(operacion_id, miembro, evento_actual):
        if not isinstance(evento_actual, dict) or evento_actual.get("operacion_id") != operacion_id:
            return False
        miembros = evento_actual.get("miembros")
        if not isinstance(miembros, list):
            return False
        actual = next((m for m in miembros if isinstance(m, dict)
                       and m.get("tipo_elemento") == "carpeta"
                       and m.get("recurso_id") == miembro.get("recurso_id")), None)
        return bool(actual and actual.get("generacion_id") == miembro.get("generacion_id"))

    @_controlar_base_datos
    def restaurar(self, *, solicitante_id, organizacion_id, carpeta_id):
        actor, org, raiz_id = map(identificador,
                                  (solicitante_id, organizacion_id, carpeta_id))
        evento, manifiesto = self._manifiesto(raiz_id, org)
        ids_archivo = sorted((UUID(m["recurso_id"]) for m in manifiesto["miembros"]
                              if isinstance(m, dict) and m.get("tipo_elemento") == "archivo"),
                             key=str)
        with ExitStack() as reclamos:
            comprobaciones = [reclamos.enter_context(self.repo.reclamar(i)) for i in ids_archivo]
            with self.repo.transaccion(org):
                for comprobar in comprobaciones:
                    comprobar()
                nivel = self.repo.nivel(actor, org)
                if nivel not in (0, 3):
                    raise PermissionDenied()
                raiz = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                    pk=raiz_id, organizacion_id=org, en_papelera=True).first()
                if raiz is None:
                    raise NotFound()
                if self.repo.lote_purga_pendiente(org, raiz.pk):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                evento_actual, manifiesto_actual = self._manifiesto(raiz.pk, org)
                if not self._manifiesto_sigue_vigente(
                        (evento, manifiesto), (evento_actual, manifiesto_actual)):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                manifiesto = manifiesto_actual
                ahora = self.reloj()
                if (raiz.fecha_papelera is None or timezone.is_naive(raiz.fecha_papelera)
                        or timezone.is_naive(ahora) or raiz.fecha_papelera > ahora):
                    raise ErrorPapelera()
                if nivel == 3:
                    autorizar_envio(nivel, self.repo.permisos(
                        actor, SimpleNamespace(pk=None, carpeta_id=raiz.pk,
                                               organizacion_id=org)))
                carpetas, archivos = [], []
                for miembro in manifiesto["miembros"]:
                    if (not isinstance(miembro, dict) or miembro.get("tipo_elemento") not in
                            {"carpeta", "archivo"}):
                        raise ErrorPapelera()
                    try:
                        recurso_id = UUID(miembro["recurso_id"])
                    except (KeyError, ValueError, TypeError):
                        raise ErrorPapelera() from None
                    if miembro["tipo_elemento"] == "carpeta":
                        fila = Carpeta.objects.using(self.repo.using).select_for_update().filter(
                            pk=recurso_id, organizacion_id=org, en_papelera=True).first()
                        if fila and fila.fecha_papelera == raiz.fecha_papelera:
                            if self.repo.lote_purga_pendiente(org, fila.pk):
                                raise ErrorPapelera("RESOURCE_BUSY", 409)
                            evento_miembro = LogAuditoria.objects.using(self.repo.using).filter(
                                organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
                                detalles__version=1,
                                detalles__miembros__contains=[{"recurso_id": str(fila.pk)}],
                            ).order_by("-id").first()
                            detalles_miembro = evento_miembro.detalles if evento_miembro else None
                            if self._generacion_carpeta_vigente(
                                    manifiesto["operacion_id"], miembro, detalles_miembro):
                                carpetas.append((fila, miembro))
                    else:
                        fila = Archivo.objects.using(self.repo.using).select_for_update().filter(
                            pk=recurso_id, organizacion_id=org, en_papelera=True).first()
                        if not fila or fila.fecha_papelera != raiz.fecha_papelera:
                            continue
                        ultimo = self.repo.ultimo_evento(fila)
                        if ultimo is None or ultimo.detalles.get("generacion_id") != miembro.get("generacion_id"):
                            continue
                        if self.repo.purga_pendiente(fila):
                            raise ErrorPapelera("RESOURCE_BUSY", 409)
                        archivos.append((fila, miembro))
                if not carpetas or not any(f.pk == raiz.pk for f, _ in carpetas):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                if nivel == 3:
                    for carpeta, _ in carpetas:
                        autorizar_envio(nivel, self.repo.permisos(actor, SimpleNamespace(
                            pk=None, carpeta_id=carpeta.pk, organizacion_id=org)))
                    for archivo, _ in archivos:
                        autorizar_envio(nivel, self.repo.permisos(actor, archivo))
                ids_lote_carpetas = {f.pk for f, _ in carpetas}
                raiz_destino = raiz.padre_id
                padre_raiz = Carpeta.objects.using(self.repo.using).filter(
                    pk=raiz_destino, organizacion_id=org, en_papelera=False).first() if raiz_destino else None
                if raiz_destino and padre_raiz is None:
                    raiz_destino = None
                miembros_activos = carpetas + archivos
                nombres = set()
                for fila, miembro in miembros_activos:
                    original = UUID(miembro["padre_id"]) if miembro.get("padre_id") else None
                    destino = raiz_destino if fila.pk == raiz.pk else original
                    if destino is not None and destino not in ids_lote_carpetas:
                        padre = Carpeta.objects.using(self.repo.using).filter(
                            pk=destino, organizacion_id=org, en_papelera=False).first()
                        if padre is None:
                            raise ErrorPapelera("VALIDATION_ERROR", 409)
                        if nivel == 3:
                            try:
                                autorizar_envio(nivel, self.repo.permisos(actor, SimpleNamespace(
                                    pk=None, carpeta_id=destino, organizacion_id=org)))
                            except NotFound:
                                # El destino existe dentro del ámbito; ocultarlo como 404
                                # confundiría una denegación con un recurso inexistente.
                                raise PermissionDenied() from None
                    if not self.repo.nombre_disponible(org, destino, fila.nombre,
                            excluir_carpeta=fila.pk if isinstance(fila, Carpeta) else None,
                            excluir_archivo=fila.pk if isinstance(fila, Archivo) else None):
                        raise ErrorPapelera("VALIDATION_ERROR", 409, fields={
                            "nombre": ["Ya existe un recurso con ese nombre."]})
                    clave = (str(destino), normalize("NFC", fila.nombre).casefold())
                    if clave in nombres:
                        raise ErrorPapelera("VALIDATION_ERROR", 409)
                    nombres.add(clave)
                limite, usado, reservas = self.repo.capacidad(org, ahora)
                bytes_a_reactivar = sum(f.tamano_bytes for f, _ in archivos)
                if bytes_a_reactivar and usado + reservas + bytes_a_reactivar > limite:
                    raise ErrorPapelera("CUOTA_EXCEDIDA", 409)
                for carpeta, miembro in sorted(carpetas, key=lambda x: str(x[0].pk)):
                    destino = raiz_destino if carpeta.pk == raiz.pk else carpeta.padre_id
                    carpeta.padre_id, carpeta.en_papelera, carpeta.fecha_papelera = destino, False, None
                    carpeta.save(using=self.repo.using,
                                 update_fields=["padre", "en_papelera", "fecha_papelera"])
                for archivo, miembro in archivos:
                    destino = UUID(miembro["padre_id"]) if miembro.get("padre_id") else None
                    archivo.carpeta_id, archivo.en_papelera, archivo.fecha_papelera = destino, False, None
                    archivo.save(using=self.repo.using,
                                 update_fields=["carpeta", "en_papelera", "fecha_papelera", "actualizado_en"])
                    self.repo.evento_restauracion(archivo, actor, miembro["generacion_id"])
                LogAuditoria.objects.using(self.repo.using).create(
                    usuario_id=actor, organizacion_id=org,
                    accion="PAPELERA_CARPETA_RESTAURADA", detalles={
                        "version": 1, "operacion_id": manifiesto["operacion_id"],
                        "manifiesto_id": evento.pk, "raiz_id": str(raiz.pk),
                        "miembros_restaurados": [m["recurso_id"] for _, m in miembros_activos],
                    })


def listar_raices_carpeta(org, *, using="default"):
    eventos = LogAuditoria.objects.using(using).filter(
        organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
        detalles__version=1, detalles__cerrado=True).order_by("-id")
    resultado, vistas = [], set()
    for evento in eventos:
        d = evento.detalles
        if not isinstance(d, dict) or not d.get("raiz_id") or d["raiz_id"] in vistas:
            continue
        vistas.add(d["raiz_id"])
        try:
            carpeta = Carpeta.objects.using(using).filter(
                pk=UUID(d["raiz_id"]), organizacion_id=org, en_papelera=True).first()
        except (ValueError, TypeError):
            continue
        if carpeta is None or carpeta.fecha_papelera is None:
            continue
        if (d.get("version") != 1 or not d.get("operacion_id")
                or not isinstance(d.get("miembros"), list)
                or len(d["miembros"]) > LIMITE_LOTE_CARPETA):
            raise ErrorPapelera()
        raiz = next((m for m in d["miembros"] if isinstance(m, dict)
                     and m.get("tipo_elemento") == "carpeta"
                     and m.get("recurso_id") == str(carpeta.pk)), None)
        if raiz is None or raiz.get("generacion_id") != d.get("raiz_generacion_id"):
            raise ErrorPapelera()
        if LogAuditoria.objects.using(using).filter(
                organizacion_id=org, accion="PAPELERA_CARPETA_RESTAURADA",
                detalles__operacion_id=d.get("operacion_id")).exists():
            continue
        miembros = d["miembros"] if isinstance(d.get("miembros"), list) else []
        resultado.append({
            "id": str(carpeta.pk), "nombre": carpeta.nombre, "tipo_elemento": "carpeta",
            "eliminado_en": carpeta.fecha_papelera.isoformat(),
            "expira_en": (carpeta.fecha_papelera + timedelta(days=30)).isoformat(),
            "dias_restantes": max(0, ceil((carpeta.fecha_papelera + timedelta(days=30)
                                           - timezone.now()).total_seconds() / 86400)),
            "cantidad_elementos": len(miembros), "tamano_bytes": sum(
                m.get("tamano_bytes", 0) for m in miembros if isinstance(m, dict)),
        })
    return resultado
