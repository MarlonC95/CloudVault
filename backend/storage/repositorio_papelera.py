"""Adaptador de tablas existentes; no instala SQL ni modifica el contador de cuota."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.db import connections, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from almacenamiento.persistencia import RepositorioCargas
from auth_workspaces.models import LogAuditoria
from .models import Archivo, Carpeta
from .papelera import ErrorPapelera


@dataclass(frozen=True)
class CandidatoPurga:
    organizacion_id: object
    archivo_id: object
    fecha_papelera: datetime | None
    generacion_id: str | None
    clave_s3: str | None
    operacion_id: str | None = None
    es_recuperacion: bool = False


ESPERAS_REINTENTO_MINUTOS = (1, 2, 4, 8, 16, 32, 60)


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

    def purga_pendiente(self, archivo, *, excluir_operacion_lote=None):
        return (self.intencion_pendiente(archivo) is not None
                or self.lote_purga_pendiente(
                    archivo.organizacion_id, archivo.pk,
                    excluir_operacion=excluir_operacion_lote))

    def lote_purga_pendiente(self, organizacion_id, recurso_id, *, excluir_operacion=None):
        """Una selección durable de carpeta/vaciado bloquea miembros incompatibles."""
        eventos = LogAuditoria.objects.using(self.using).filter(
            organizacion_id=organizacion_id,
            accion__in=("PAPELERA_CARPETA_PURGA_SOLICITADA", "PAPELERA_VACIADO_INICIADO"),
            detalles__version=1, detalles__miembros__contains=[{"recurso_id": str(recurso_id)}],
        ).order_by("-id")
        pagina = list(eventos[:101])
        if len(pagina) > 100:
            raise ErrorPapelera()
        for evento in pagina:
            d = evento.detalles
            if not isinstance(d, dict) or not d.get("operacion_id"):
                raise ErrorPapelera()
            if d["operacion_id"] == excluir_operacion:
                continue
            cierre = ("PAPELERA_CARPETA_PURGADA" if evento.accion == "PAPELERA_CARPETA_PURGA_SOLICITADA"
                      else "PAPELERA_VACIADO_CERRADO")
            if not LogAuditoria.objects.using(self.using).filter(
                    organizacion_id=organizacion_id, accion=cierre,
                    detalles__version=1, detalles__operacion_id=d["operacion_id"]).exists():
                return True
        return False

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

    def seleccionar_candidatos_purga(self, *, corte, ahora, limite, organizacion_id=None):
        """Devuelve hasta `limite` candidatos listos sin retener más de 100 filas."""
        if type(limite) is not int or not 1 <= limite <= 100:
            raise ValueError("Límite de purga inválido")
        self.incompatibles_ultima_seleccion = 0
        org = organizacion_id
        fechas_invalidas = Archivo.objects.using(self.using).filter(
            en_papelera=True, fecha_papelera__isnull=True)
        fechas_futuras = Archivo.objects.using(self.using).filter(
            en_papelera=True, fecha_papelera__gt=ahora)
        if org is not None:
            fechas_invalidas = fechas_invalidas.filter(organizacion_id=org)
            fechas_futuras = fechas_futuras.filter(organizacion_id=org)
        self.incompatibles_ultima_seleccion = fechas_invalidas.count() + fechas_futuras.count()
        filtro = Archivo.objects.using(self.using).filter(
            en_papelera=True, fecha_papelera__isnull=False, fecha_papelera__lte=corte)
        if org is not None:
            filtro = filtro.filter(organizacion_id=org)
        # Reservar capacidad para ambos conjuntos evita que un flujo sostenido
        # de vencidos deje sin turno las intenciones manuales incompletas.
        franja = int(ahora.timestamp() // (15 * 60))
        cupo_vencidos = (limite // 2 if limite > 1 else (1 if franja % 2 == 0 else 0))
        candidatos, vistos = [], set()
        cantidad_vencidos = filtro.count()
        offset_vencidos = (franja * max(1, cupo_vencidos)) % cantidad_vencidos if cantidad_vencidos else 0
        examinados_vencidos = 0
        while (len(candidatos) < cupo_vencidos and examinados_vencidos < 1000
               and examinados_vencidos < cantidad_vencidos):
            fin = min(offset_vencidos + 100, cantidad_vencidos)
            filas = list(filtro.order_by("fecha_papelera", "id").values(
                "id", "organizacion_id", "fecha_papelera")[offset_vencidos:fin])
            if not filas:
                break
            examinados_vencidos += len(filas)
            for fila in filas:
                cursor_id = fila["id"]
                if fila["organizacion_id"] is None:
                    self.incompatibles_ultima_seleccion += 1
                    continue
                archivo = Archivo.objects.using(self.using).filter(
                    pk=cursor_id, organizacion_id=fila["organizacion_id"]).first()
                if archivo is None:
                    continue
                try:
                    pendiente = self.intencion_pendiente(archivo)
                except ErrorPapelera:
                    self.incompatibles_ultima_seleccion += 1
                    continue
                # Las recuperaciones tienen su propio cupo y recorrido; una
                # espera pendiente no debe tapar vencidos posteriores.
                if pendiente is not None:
                    continue
                try:
                    anterior = self.ultimo_evento(archivo)
                except ErrorPapelera:
                    self.incompatibles_ultima_seleccion += 1
                    continue
                generacion = anterior.detalles.get("generacion_id") if anterior else None
                candidato = CandidatoPurga(archivo.organizacion_id, archivo.pk,
                                           archivo.fecha_papelera, generacion,
                                           archivo.clave_s3)
                candidatos.append(candidato)
                vistos.add((str(candidato.organizacion_id), str(candidato.archivo_id), None))
                if len(candidatos) >= cupo_vencidos:
                    break
            offset_vencidos = 0 if fin >= cantidad_vencidos else fin

        restantes = limite - len(candidatos)
        if restantes > 0:
            eventos = LogAuditoria.objects.using(self.using).filter(
                accion="PAPELERA_PURGA_SOLICITADA", detalles__tipo_elemento="archivo")
            if org is not None:
                eventos = eventos.filter(organizacion_id=org)
            total_eventos = eventos.count()
            offset_eventos = (franja * max(1, restantes)) % total_eventos if total_eventos else 0
            examinados_eventos = 0
            while restantes > 0 and examinados_eventos < 1000 and examinados_eventos < total_eventos:
                fin = min(offset_eventos + 100, total_eventos)
                pagina = list(eventos.order_by("id")[offset_eventos:fin])
                if not pagina:
                    break
                examinados_eventos += len(pagina)
                for evento in pagina:
                    d = evento.detalles
                    if (not isinstance(d, dict) or d.get("version") != 1
                            or not d.get("operacion_id") or not d.get("generacion_id")
                            or not d.get("recurso_id") or not isinstance(d.get("clave_s3"), str)):
                        self.incompatibles_ultima_seleccion += 1
                        continue
                    cerrada = LogAuditoria.objects.using(self.using).filter(
                        organizacion_id=evento.organizacion_id, accion="PAPELERA_PURGADO",
                        detalles__version=1, detalles__operacion_id=d["operacion_id"],
                        detalles__generacion_id=d["generacion_id"]).exists()
                    if cerrada:
                        continue
                    try:
                        archivo_id = UUID(d["recurso_id"])
                    except (ValueError, TypeError):
                        continue
                    archivo = Archivo.objects.using(self.using).filter(
                        pk=archivo_id, organizacion_id=evento.organizacion_id).first()
                    if archivo is None:
                        self.incompatibles_ultima_seleccion += 1
                        continue
                    try:
                        actual = self.intencion_pendiente(archivo)
                    except ErrorPapelera:
                        self.incompatibles_ultima_seleccion += 1
                        continue
                    if actual is None or actual.detalles.get("operacion_id") != d["operacion_id"]:
                        continue
                    if not self.reintento_purga_vencido(archivo, actual.detalles, ahora):
                        continue
                    candidato = self._candidato_intencion(archivo, actual.detalles)
                    if candidato is None:
                        continue
                    clave = (str(candidato.organizacion_id), str(candidato.archivo_id), candidato.operacion_id)
                    if clave in vistos:
                        continue
                    candidatos.append(candidato)
                    vistos.add(clave)
                    restantes -= 1
                    if restantes <= 0:
                        break
                offset_eventos = 0 if fin >= total_eventos else fin
        return candidatos

    def purgar_carpetas_vacias_vencidas(self, *, corte, limite, organizacion_id=None,
                                        simular=False):
        """Retira solo contenedores vencidos que ya no tienen hojas ni subcarpetas."""
        if type(limite) is not int or not 0 <= limite <= 100:
            raise ValueError("Límite de contenedores inválido")
        if limite == 0:
            return 0
        filtro = Carpeta.objects.using(self.using).filter(
            en_papelera=True, fecha_papelera__isnull=False, fecha_papelera__lte=corte)
        archivos_hijos = Archivo.objects.using(self.using).filter(carpeta_id=OuterRef("pk"))
        carpetas_hijas = Carpeta.objects.using(self.using).filter(padre_id=OuterRef("pk"))
        filtro = filtro.annotate(_tiene_archivos=Exists(archivos_hijos),
                                 _tiene_carpetas=Exists(carpetas_hijas)).filter(
            _tiene_archivos=False, _tiene_carpetas=False)
        if organizacion_id is not None:
            filtro = filtro.filter(organizacion_id=organizacion_id)
        candidatos = list(filtro.order_by("fecha_papelera", "id").values_list(
            "id", "organizacion_id", "fecha_papelera")[:limite])
        purgadas = 0
        for carpeta_id, org, fecha in candidatos:
            if org is None:
                continue
            if simular:
                carpeta = Carpeta.objects.using(self.using).filter(
                    pk=carpeta_id, organizacion_id=org, en_papelera=True,
                    fecha_papelera=fecha, fecha_papelera__lte=corte).first()
                if carpeta is None or self.lote_purga_pendiente(org, carpeta.pk):
                    continue
                if (Archivo.objects.using(self.using).filter(carpeta_id=carpeta.pk).exists()
                        or Carpeta.objects.using(self.using).filter(padre_id=carpeta.pk).exists()):
                    continue
                ultimo = LogAuditoria.objects.using(self.using).filter(
                        organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
                        detalles__version=1,
                        detalles__miembros__contains=[{"recurso_id": str(carpeta.pk)}],
                ).order_by("-id").first()
                if (ultimo is None or not isinstance(ultimo.detalles, dict)
                        or ultimo.detalles.get("fecha_papelera") != fecha.isoformat()):
                    continue
                purgadas += 1
                continue
            with self.transaccion(org):
                carpeta = Carpeta.objects.using(self.using).select_for_update().filter(
                    pk=carpeta_id, organizacion_id=org, en_papelera=True,
                    fecha_papelera=fecha, fecha_papelera__lte=corte).first()
                if carpeta is None:
                    continue
                if self.lote_purga_pendiente(org, carpeta.pk):
                    continue
                if (Archivo.objects.using(self.using).filter(carpeta_id=carpeta.pk).exists()
                        or Carpeta.objects.using(self.using).filter(padre_id=carpeta.pk).exists()):
                    continue
                ultimo = LogAuditoria.objects.using(self.using).filter(
                    organizacion_id=org, accion="PAPELERA_CARPETA_ENVIADA",
                    detalles__version=1,
                    detalles__miembros__contains=[{"recurso_id": str(carpeta.pk)}],
                ).order_by("-id").first()
                miembro = None
                if ultimo and isinstance(ultimo.detalles, dict):
                    miembro = next((m for m in ultimo.detalles.get("miembros", [])
                                    if isinstance(m, dict)
                                    and m.get("recurso_id") == str(carpeta.pk)), None)
                if miembro is None:
                    continue
                if (not isinstance(ultimo.detalles, dict)
                        or ultimo.detalles.get("fecha_papelera") != fecha.isoformat()):
                    continue
                carpeta.delete(using=self.using)
                LogAuditoria.objects.using(self.using).create(
                    usuario_id=None, organizacion_id=org,
                    accion="PAPELERA_CARPETA_RECURSO_PURGADO", detalles={
                        "version": 1, "recurso_id": str(carpeta_id),
                        "generacion_id": miembro.get("generacion_id"),
                        "fecha_papelera": fecha.isoformat(),
                        "contenedor_vacio": True,
                    })
                purgadas += 1
        return purgadas

    def _candidato_intencion(self, archivo, detalles):
        if (archivo.organizacion_id is None or archivo.fecha_papelera is None
                or timezone.is_naive(archivo.fecha_papelera)
                or not isinstance(detalles.get("clave_s3"), str)):
            self.incompatibles_ultima_seleccion += 1
            return None
        return CandidatoPurga(archivo.organizacion_id, archivo.pk, archivo.fecha_papelera,
                              detalles.get("generacion_id"), detalles.get("clave_s3"),
                              detalles.get("operacion_id"), True)

    def reintento_purga_vencido(self, archivo, intencion, ahora):
        ultimo = self._eventos_archivo(archivo).filter(
            accion="PAPELERA_PURGA_REINTENTO",
            detalles__operacion_id=intencion["operacion_id"],
            detalles__generacion_id=intencion["generacion_id"]).order_by("-id").first()
        if ultimo is None:
            return True
        detalles = ultimo.detalles
        if not isinstance(detalles, dict):
            return False
        if "reintentar_en" not in detalles:
            # Auditorías anteriores a fase 4 se pueden recuperar una vez.
            return True
        reintentar = detalles.get("reintentar_en")
        if not isinstance(reintentar, str):
            self.incompatibles_ultima_seleccion += 1
            return False
        try:
            fecha = datetime.fromisoformat(reintentar)
        except ValueError:
            self.incompatibles_ultima_seleccion += 1
            return False
        if not timezone.is_aware(fecha):
            self.incompatibles_ultima_seleccion += 1
            return False
        return fecha <= ahora

    def validar_candidato(self, archivo, candidato, ahora):
        if not self.validar_identidad_candidato(archivo, candidato):
            return False
        if candidato.operacion_id:
            return True
        return archivo.fecha_papelera <= ahora - timedelta(days=30)

    def validar_identidad_candidato(self, archivo, candidato):
        if (not archivo.en_papelera or archivo.fecha_papelera is None
                or timezone.is_naive(archivo.fecha_papelera)
                or archivo.organizacion_id != candidato.organizacion_id
                or archivo.pk != candidato.archivo_id
                or archivo.fecha_papelera != candidato.fecha_papelera
                or archivo.clave_s3 != candidato.clave_s3):
            return False
        anterior = self.ultimo_evento(archivo)
        generacion = anterior.detalles.get("generacion_id") if anterior else None
        if generacion != candidato.generacion_id:
            return False
        if candidato.operacion_id:
            intencion = self.intencion_pendiente(archivo)
            return bool(intencion and intencion.detalles.get("operacion_id") == candidato.operacion_id
                        and intencion.detalles.get("generacion_id") == candidato.generacion_id
                        and intencion.detalles.get("fecha_papelera") == archivo.fecha_papelera.isoformat()
                        and intencion.detalles.get("clave_s3") == archivo.clave_s3)
        return True

    def reintento_candidato_vencido(self, archivo, candidato, ahora):
        intencion = self.intencion_pendiente(archivo)
        return bool(intencion
                    and intencion.detalles.get("operacion_id") == candidato.operacion_id
                    and self.reintento_purga_vencido(archivo, intencion.detalles, ahora))

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

    def auditar_reintento_purga(self, archivo, actor, intencion, motivo, *, ahora=None,
                                bytes_fisicos_confirmados=0):
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
        detalles["motivo"] = motivo if motivo in {
            "S3", "AUSENCIA_NO_CONFIRMADA", "CIERRE", "INCOMPATIBLE"
        } else "S3"
        reloj = ahora or timezone.now()
        if timezone.is_naive(reloj):
            raise ErrorPapelera()
        minutos = ESPERAS_REINTENTO_MINUTOS[min(previo, len(ESPERAS_REINTENTO_MINUTOS) - 1)]
        detalles["reintentar_en"] = (reloj + timedelta(minutes=minutos)).isoformat()
        if type(bytes_fisicos_confirmados) is not int or bytes_fisicos_confirmados < 0:
            raise ErrorPapelera()
        anteriores = self._eventos_archivo(archivo).filter(
            accion="PAPELERA_PURGA_REINTENTO",
            detalles__operacion_id=intencion["operacion_id"],
            detalles__generacion_id=intencion["generacion_id"],
        ).order_by("-id").first()
        previo_bytes = (anteriores.detalles.get("bytes_fisicos_confirmados", 0)
                        if anteriores and isinstance(anteriores.detalles, dict) else 0)
        if type(previo_bytes) is not int or previo_bytes < 0:
            raise ErrorPapelera()
        detalles["bytes_fisicos_confirmados"] = max(previo_bytes, bytes_fisicos_confirmados)
        self._crear_evento(archivo, actor, "PAPELERA_PURGA_REINTENTO", detalles)
        return detalles

    def referencia_incompatible(self, archivo, clave):
        if Archivo.objects.using(self.using).filter(clave_s3=clave).exclude(pk=archivo.pk).exists():
            return True
        from almacenamiento.models import IntentoPublicacion
        return IntentoPublicacion.objects.using(self.using).filter(
            clave_final=clave).exclude(sesion__archivo_id=archivo.pk).exists()

    def cerrar_purga(self, archivo, actor, intencion, *, bytes_fisicos_purgados=0):
        if type(bytes_fisicos_purgados) is not int or bytes_fisicos_purgados < 0:
            raise ErrorPapelera()
        actual = self.intencion_pendiente(archivo)
        if actual is None or actual.detalles.get("operacion_id") != intencion["operacion_id"]:
            raise ErrorPapelera()
        detalles = actual.detalles
        ultimo_reintento = self._eventos_archivo(archivo).filter(
            accion="PAPELERA_PURGA_REINTENTO",
            detalles__operacion_id=intencion["operacion_id"],
            detalles__generacion_id=intencion["generacion_id"],
        ).order_by("-id").first()
        previos_confirmados = (ultimo_reintento.detalles.get("bytes_fisicos_confirmados", 0)
                               if ultimo_reintento and isinstance(ultimo_reintento.detalles, dict) else 0)
        if type(previos_confirmados) is not int or previos_confirmados < 0:
            raise ErrorPapelera()
        bytes_fisicos_purgados = max(bytes_fisicos_purgados, previos_confirmados)
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
                "fecha_papelera": detalles["fecha_papelera"],
                "origen": detalles.get("origen", "MANUAL"),
                "bytes_fisicos_purgados": bytes_fisicos_purgados,
                "cuota_liberada_bytes": 0,
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
