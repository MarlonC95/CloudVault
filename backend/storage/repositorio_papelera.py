"""Adaptador de tablas existentes; no instala SQL ni modifica el contador de cuota."""

from contextlib import contextmanager
from uuid import UUID, uuid4

from django.db import connections, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from almacenamiento.persistencia import RepositorioCargas
from auth_workspaces.models import LogAuditoria
from .models import Archivo, Carpeta
from .papelera import ErrorPapelera


class RepositorioPapelera:
    def __init__(self, *, using="default"):
        self.using = using
        self.cargas = RepositorioCargas(using=using)

    def reclamar(self, archivo_id):
        return self.cargas.reclamar_publicador(archivo_id=archivo_id)

    @contextmanager
    def transaccion(self, organizacion_id):
        with transaction.atomic(using=self.using, durable=True):
            with self.cargas.unidad_de_trabajo(organizacion_id=organizacion_id):
                yield

    def nivel(self, actor, org):
        # Revalidar y bloquear la membresía y el estado de cuenta antes de mutar.
        with connections[self.using].cursor() as cursor:
            cursor.execute("""SELECT m.nivel_rol FROM miembros_organizacion m
                JOIN usuarios u ON u.id = m.usuario_id
                WHERE m.usuario_id = %s AND m.organizacion_id = %s AND u.esta_activo
                FOR UPDATE OF m, u""", [actor, org])
            fila = cursor.fetchone()
        if fila is None:
            raise NotFound()
        return fila[0]

    def archivo(self, archivo_id, org):
        return Archivo.objects.using(self.using).select_for_update().filter(
            pk=archivo_id, organizacion_id=org).first()

    def permisos(self, actor, archivo, bloquear=True):
        carpetas, visitadas = [], set()
        padre = archivo.carpeta_id
        while padre is not None:
            if padre in visitadas or len(visitadas) >= 1000:
                raise ErrorPapelera()
            visitadas.add(padre)
            carpetas_qs = Carpeta.objects.using(self.using)
            if bloquear: carpetas_qs = carpetas_qs.select_for_update()
            carpeta = carpetas_qs.filter(pk=padre, organizacion_id=archivo.organizacion_id).first()
            if carpeta is None:
                # Un padre desaparecido no revoca una concesión directa al archivo.
                # Una referencia que cruza ámbitos sí es inconsistente.
                if Carpeta.objects.using(self.using).filter(pk=padre).exists():
                    raise ErrorPapelera()
                break
            carpetas.append(padre)
            padre = carpeta.padre_id
        with connections[self.using].cursor() as cursor:
            cursor.execute("""SELECT tipo_permiso FROM permisos_recurso
                WHERE usuario_id = %s AND (archivo_id = %s OR carpeta_id = ANY(%s::uuid[]))
                """ + (" FOR SHARE" if bloquear else ""), [actor, archivo.pk, carpetas])
            return [fila[0] for fila in cursor.fetchall()]

    def purga_pendiente(self, archivo):
        return self.intencion_pendiente(archivo) is not None

    def _eventos_archivo(self, archivo):
        return LogAuditoria.objects.using(self.using).filter(
            organizacion_id=archivo.organizacion_id,
            detalles__recurso_id=str(archivo.pk), detalles__tipo_elemento="archivo")

    def intencion_pendiente(self, archivo):
        eventos = self._eventos_archivo(archivo)
        solicitudes = list(eventos.filter(accion="PAPELERA_PURGA_SOLICITADA")
                           .order_by("-id")[:101])
        if len(solicitudes) > 100:
            raise ErrorPapelera()
        pendientes = []
        for evento in solicitudes:
            d = evento.detalles
            if (not isinstance(d, dict) or d.get("version") != 1
                    or not d.get("operacion_id") or not d.get("generacion_id")
                    or d.get("recurso_id") != str(archivo.pk)
                    or not isinstance(d.get("clave_s3"), str)):
                raise ErrorPapelera()
            cerrada = eventos.filter(accion="PAPELERA_PURGADO", detalles__version=1,
                                     detalles__operacion_id=d["operacion_id"],
                                     detalles__generacion_id=d["generacion_id"]).exists()
            if not cerrada:
                pendientes.append(evento)
        if len(pendientes) > 1:
            raise ErrorPapelera()
        return pendientes[0] if pendientes else None

    def recorrer_intenciones_pendientes(self, organizacion_id, *, limite=100):
        """Escanea por páginas acotadas; cada barrido nuevo debe iniciar sin cursor.

        Se conserva solo una página en memoria. El llamador puede consumir el
        iterador hasta `limite`; el siguiente barrido vuelve a empezar desde el
        principio para no perder una intención comprometida tarde con ID anterior.
        """
        if type(limite) is not int or not 1 <= limite <= 100:
            raise ValueError("Límite de recuperación inválido")
        eventos = LogAuditoria.objects.using(self.using).filter(
            organizacion_id=organizacion_id, detalles__tipo_elemento="archivo")
        solicitudes = eventos.filter(accion="PAPELERA_PURGA_SOLICITADA")
        cursor_id = 0
        entregados = 0
        while entregados < limite:
            pagina = list(solicitudes.filter(id__gt=cursor_id).order_by("id")[:100])
            if not pagina:
                return
            for evento in pagina:
                cursor_id = evento.id
                detalles = evento.detalles
                if (not isinstance(detalles, dict) or detalles.get("version") != 1
                        or not detalles.get("operacion_id") or not detalles.get("generacion_id")
                        or not detalles.get("recurso_id") or not isinstance(detalles.get("clave_s3"), str)):
                    raise ErrorPapelera()
                cerrada = eventos.filter(
                    accion="PAPELERA_PURGADO", detalles__version=1,
                    detalles__operacion_id=detalles["operacion_id"],
                    detalles__generacion_id=detalles["generacion_id"]).exists()
                if not cerrada:
                    yield evento
                    entregados += 1
                    if entregados >= limite:
                        return
            if len(pagina) < 100:
                return

    def generar_o_reutilizar_intencion(self, archivo, actor, origen="MANUAL"):
        existente = self.intencion_pendiente(archivo)
        ahora = archivo.fecha_papelera
        if ahora is None or timezone.is_naive(ahora) or ahora > timezone.now():
            raise ErrorPapelera()
        anterior = self.ultimo_evento(archivo)
        if existente is not None:
            detalles = existente.detalles
            generacion_actual = (anterior.detalles.get("generacion_id")
                                 if anterior and anterior.accion in
                                 ("PAPELERA_ENVIADO", "PAPELERA_GENERACION_ADOPTADA") else None)
            if (detalles["clave_s3"] != archivo.clave_s3
                    or detalles.get("fecha_papelera") != ahora.isoformat()
                    or detalles.get("generacion_id") != generacion_actual):
                raise ErrorPapelera()
            return detalles

        if anterior is None:
            generacion = str(uuid4())
            self.evento_restauracion(archivo, actor, generacion, "PAPELERA_GENERACION_ADOPTADA")
            # El evento anterior al de purga se escribe dentro de la misma
            # transacción y adopta la fecha existente sin alterar retención.
        elif anterior.accion in ("PAPELERA_ENVIADO", "PAPELERA_GENERACION_ADOPTADA"):
            detalles_previos = anterior.detalles
            generacion = detalles_previos.get("generacion_id")
            if (detalles_previos.get("version") != 1 or not generacion
                    or detalles_previos.get("fecha_papelera") not in (None, ahora.isoformat())):
                raise ErrorPapelera()
        else:
            raise ErrorPapelera()

        detalles = {
            "version": 1, "operacion_id": str(uuid4()),
            "generacion_id": generacion, "tipo_elemento": "archivo",
            "recurso_id": str(archivo.pk), "fecha_papelera": ahora.isoformat(),
            "origen": origen, "clave_s3": archivo.clave_s3,
            "intento": 0,
        }
        self._crear_evento(archivo, actor, "PAPELERA_PURGA_SOLICITADA", detalles)
        return detalles

    def _crear_evento(self, archivo, actor, accion, detalles):
        LogAuditoria.objects.using(self.using).create(
            usuario_id=actor, organizacion_id=archivo.organizacion_id,
            accion=accion, detalles=detalles)

    def auditar_reintento_purga(self, archivo, actor, intencion, motivo):
        detalles = dict(intencion)
        ultimo = self._eventos_archivo(archivo).filter(
            accion="PAPELERA_PURGA_REINTENTO",
            detalles__operacion_id=intencion["operacion_id"],
            detalles__generacion_id=intencion["generacion_id"],
        ).order_by("-id").first()
        previo = ultimo.detalles.get("intento", 0) if ultimo and isinstance(ultimo.detalles, dict) else 0
        if type(previo) is not int or previo < 0 or previo >= 1000000:
            raise ErrorPapelera()
        detalles["intento"] = previo + 1
        detalles["motivo"] = motivo if motivo in {"S3", "AUSENCIA_NO_CONFIRMADA", "CIERRE"} else "S3"
        self._crear_evento(archivo, actor, "PAPELERA_PURGA_REINTENTO", detalles)
        return detalles

    def referencia_incompatible(self, archivo, clave):
        if Archivo.objects.using(self.using).filter(clave_s3=clave).exclude(pk=archivo.pk).exists():
            return True
        from almacenamiento.models import IntentoPublicacion
        return IntentoPublicacion.objects.using(self.using).filter(
            clave_final=clave).exclude(sesion__archivo_id=archivo.pk).exists()

    def cerrar_purga(self, archivo, actor, intencion):
        actual = self.intencion_pendiente(archivo)
        if actual is None or actual.detalles.get("operacion_id") != intencion["operacion_id"]:
            raise ErrorPapelera()
        detalles = actual.detalles
        generacion = self.ultimo_evento(archivo)
        if (archivo.pk != UUID(detalles["recurso_id"])
                or archivo.clave_s3 != detalles["clave_s3"]
                or not archivo.en_papelera
                or archivo.fecha_papelera is None
                or detalles.get("fecha_papelera") != archivo.fecha_papelera.isoformat()
                or detalles.get("generacion_id") != intencion.get("generacion_id")
                or generacion is None
                or generacion.accion not in ("PAPELERA_ENVIADO", "PAPELERA_GENERACION_ADOPTADA")
                or generacion.detalles.get("generacion_id") != detalles.get("generacion_id")
                or self.referencia_incompatible(archivo, detalles["clave_s3"])):
            raise ErrorPapelera()
        LogAuditoria.objects.using(self.using).create(
            usuario_id=actor, organizacion_id=archivo.organizacion_id,
            accion="PAPELERA_PURGADO", detalles={
                "version": 1, "operacion_id": detalles["operacion_id"],
                "generacion_id": detalles["generacion_id"],
                "tipo_elemento": "archivo", "recurso_id": str(archivo.pk),
                "origen": detalles.get("origen", "MANUAL"),
            })
        archivo.delete(using=self.using)

    def marcar(self, archivo, ahora):
        archivo.en_papelera, archivo.fecha_papelera = True, ahora
        archivo.save(using=self.using, update_fields=["en_papelera", "fecha_papelera", "actualizado_en"])

    def auditar(self, *, archivo, actor, detalles):
        LogAuditoria.objects.using(self.using).create(
            usuario_id=actor, organizacion_id=archivo.organizacion_id,
            accion="PAPELERA_ENVIADO", detalles=detalles)

    def ultimo_evento(self, archivo):
        evento = self._eventos_archivo(archivo).filter(
            accion__in=['PAPELERA_ENVIADO', 'PAPELERA_GENERACION_ADOPTADA', 'PAPELERA_RESTAURADO']
        ).order_by('-id').first()
        if evento is None:
            return None
        if (not isinstance(evento.detalles, dict) or evento.detalles.get("version") != 1
                or not evento.detalles.get("generacion_id")
                or evento.detalles.get("recurso_id") != str(archivo.pk)):
            raise ErrorPapelera()
        return evento

    def destino(self, archivo, actor, nivel):
        from types import SimpleNamespace
        from .permisos_papelera import autorizar_envio
        padre, visitados = archivo.carpeta_id, set()
        while padre is not None:
            if padre in visitados or len(visitados) >= 1000:
                raise ErrorPapelera()
            visitados.add(padre)
            carpeta = Carpeta.objects.using(self.using).select_for_update().filter(
                pk=padre, organizacion_id=archivo.organizacion_id).first()
            if carpeta is None or carpeta.en_papelera:
                return None
            padre = carpeta.padre_id
        if nivel == 3 and archivo.carpeta_id:
            recurso = SimpleNamespace(pk=None, carpeta_id=archivo.carpeta_id,
                                      organizacion_id=archivo.organizacion_id)
            try:
                autorizar_envio(nivel, self.permisos(actor, recurso))
            except NotFound:
                raise PermissionDenied() from None
        return archivo.carpeta_id

    def capacidad(self, org, ahora):
        from subscriptions.cuotas import leer_cuota_organizacion, SinSuscripcionVigente
        try:
            limite, usado, fin = leer_cuota_organizacion(org, using=self.using)
        except SinSuscripcionVigente:
            raise ErrorPapelera() from None
        return limite, usado, self.cargas.bytes_pendientes(organizacion_id=org, ahora=ahora)

    def reactivar(self, archivo, destino):
        archivo.carpeta_id, archivo.en_papelera, archivo.fecha_papelera = destino, False, None
        archivo.save(using=self.using, update_fields=['carpeta', 'en_papelera', 'fecha_papelera', 'actualizado_en'])

    def evento_restauracion(self, archivo, actor, generacion, accion='PAPELERA_RESTAURADO'):
        from uuid import uuid4
        LogAuditoria.objects.using(self.using).create(
            usuario_id=actor, organizacion_id=archivo.organizacion_id, accion=accion,
            detalles={'version':1, 'tipo_elemento':'archivo', 'recurso_id':str(archivo.pk),
                      'generacion_id':generacion, 'operacion_id':str(uuid4()),
                      'fecha_papelera':archivo.fecha_papelera.isoformat() if archivo.fecha_papelera else None})

    def nombre_disponible(self, org, padre, nombre, excluir_archivo=None, excluir_carpeta=None):
        return nombre_disponible(org, padre, nombre, excluir_archivo, excluir_carpeta, self.using)


def nombre_disponible(org, padre, nombre, excluir_archivo=None, excluir_carpeta=None, using='default'):
    from unicodedata import normalize
    clave = normalize('NFC', nombre).casefold()
    archivos = Archivo.objects.using(using).filter(organizacion_id=org, carpeta_id=padre, en_papelera=False)
    carpetas = Carpeta.objects.using(using).filter(organizacion_id=org, padre_id=padre, en_papelera=False)
    if excluir_archivo: archivos = archivos.exclude(pk=excluir_archivo)
    if excluir_carpeta: carpetas = carpetas.exclude(pk=excluir_carpeta)
    return not any(normalize('NFC', n).casefold() == clave for qs in (archivos, carpetas)
                   for n in qs.values_list('nombre', flat=True).iterator())
