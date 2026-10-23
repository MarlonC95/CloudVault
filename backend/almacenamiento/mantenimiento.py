"""Coordinación de fase 07. El SQL compartido y S3 nunca se reparan a ciegas.

El diario se reconstruye desde sesiones/ledger, sin cola. Cada operación toma
el reclamo de fase 05 antes de cuota -> sesión -> intento -> diario. El reclamo
permanece durante S3; las transacciones de cuota terminan antes del I/O.
"""

from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID

from django.db import DatabaseError, connections, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from auth_workspaces.models import LogAuditoria
from .configuracion_mantenimiento import PoliticaMantenimiento
from .contrato import CodigoError
from .errores import ErrorCarga
from .models import (
    EstadoMantenimiento, EstadoPublicacion, EstadoSesion, IntentoPublicacion,
    SesionCarga, TrabajoMantenimiento,
)
from .persistencia import EstadoIncompatible, IntegridadCarga, RepositorioCargas
from .s3 import ErrorS3, PREFIJO_PROPIO, nueva_clave_final


class PendienteMantenimiento(Exception):
    def __init__(self, causa, *, proximo=None):
        self.causa, self.proximo = causa, proximo


def auditar_mantenimiento(*, sesion, accion, motivo, using):
    LogAuditoria.objects.using(using).create(
        usuario_id=sesion.solicitante_id, organizacion_id=sesion.organizacion_id,
        accion=accion, detalles={"archivo_id": str(sesion.archivo_id), "motivo": motivo})


class ServicioMantenimiento:
    def __init__(self, *, servicios_factory, cliente_factory, recuperador=None,
                 repositorio=None, politica=None, auditoria=auditar_mantenimiento):
        self.servicios_factory = servicios_factory
        self.cliente_factory = cliente_factory
        self.recuperador = recuperador
        self.repo = repositorio or RepositorioCargas()
        self.politica = politica or PoliticaMantenimiento()
        self.auditoria = auditoria

    def _fuera_sql(self):
        conexion = connections[self.repo.using]
        if conexion.vendor != "postgresql" or conexion.in_atomic_block:
            raise RuntimeError("Mantenimiento requiere PostgreSQL fuera de transacción")

    @contextmanager
    def _sql(self, servicios, sesion, comprobar):
        comprobar()
        if servicios.using != self.repo.using:
            raise IntegridadCarga("Alias de mantenimiento incompatible")
        with transaction.atomic(using=self.repo.using, durable=True):
            with self.repo.unidad_de_trabajo(organizacion_id=sesion.organizacion_id):
                with servicios.bloquear_cuota(organizacion_id=sesion.organizacion_id):
                    actual = self.repo._bloquear_sesion(
                        archivo_id=sesion.archivo_id, solicitante_id=sesion.solicitante_id)
                    campos = ("id", "archivo_id", "solicitante_id", "organizacion_id",
                              "clave_temporal", "tamano_bytes", "expira_en")
                    if any(getattr(actual, c) != getattr(sesion, c) for c in campos):
                        raise IntegridadCarga("La identidad técnica cambió")
                    intento = IntentoPublicacion.objects.using(self.repo.using).select_for_update().filter(
                        sesion=actual).first()
                    yield actual, intento

    def _validar_claves(self, sesion, intento):
        prefijo = f"{PREFIJO_PROPIO}temporales/"
        if not sesion.clave_temporal.startswith(prefijo):
            raise IntegridadCarga("Temporal fuera del módulo propio")
        try:
            identificador = UUID(sesion.clave_temporal[len(prefijo):])
        except (ValueError, TypeError):
            raise IntegridadCarga("Temporal no canónico") from None
        if sesion.clave_temporal != prefijo + str(identificador):
            raise IntegridadCarga("Temporal no canónico")
        if intento is not None and intento.clave_final != nueva_clave_final(sesion.archivo_id):
            raise IntegridadCarga("Publicación no canónica")

    def _inspeccionar(self, servicios, sesion, clave, *, exige_copia):
        # El SDK propio guarda un ACK durable. Un timeout/caída anterior a ese
        # registro requiere evidencia externa real, sin inferencias por HEAD.
        ack = TrabajoMantenimiento.objects.using(self.repo.using).get(
            sesion_id=sesion.pk).copia_concluida
        evidencia = servicios.inspeccionar_objeto_tecnico(
            sesion_id=sesion.pk, organizacion_id=sesion.organizacion_id, clave=clave)
        if evidencia.referenciado:
            raise PendienteMantenimiento("REFERENCIADO")
        if exige_copia and not (ack or evidencia.copia_concluida):
            raise PendienteMantenimiento("COPY_AMBIGUO")

    def _finalizar(self, sesion, estado):
        anterior = sesion.estado
        self.repo.finalizar_sin_publicar(archivo_id=sesion.archivo_id,
            solicitante_id=sesion.solicitante_id, estado=estado)
        sesion.refresh_from_db(using=self.repo.using)
        if anterior != sesion.estado:
            self.auditoria(sesion=sesion,
                accion="CARGA_CANCELADA" if estado == EstadoSesion.CANCELED else "CARGA_VENCIDA",
                motivo="USUARIO" if estado == EstadoSesion.CANCELED else "VENCIMIENTO",
                using=self.repo.using)

    def reconstruir(self):
        """Reconstrucción acotada incluso si murió el proceso tras el commit."""
        self._fuera_sql()
        candidatos = SesionCarga.objects.using(self.repo.using).filter(
            Q(estado__in=[EstadoSesion.CONFIRMED, EstadoSesion.CANCELED, EstadoSesion.EXPIRED])
            | Q(estado=EstadoSesion.PENDING, expira_en__lte=timezone.now())
            | Q(intentopublicacion__isnull=False),
            trabajomantenimiento__isnull=True,
        ).order_by("creado_en", "id")[:self.politica.lote]
        creados = 0
        for sesion in candidatos:
            _, nuevo = TrabajoMantenimiento.objects.using(self.repo.using).get_or_create(
                sesion_id=sesion.pk)
            creados += int(nuevo)
        return creados

    def cancelar(self, *, solicitante_id, archivo_id):
        """Servicio interno por actor; no agrega una ruta pública al contrato.

        Si COPY no puede reconciliarse, registra la solicitud y devuelve PENDING
        con pendiente_reconciliacion=True; no anuncia una cancelación ficticia.
        """
        self._fuera_sql()
        if not isinstance(solicitante_id, UUID) or not isinstance(archivo_id, UUID):
            raise ValueError("La cancelación exige UUID")
        sesion = self.repo.recuperar_sesion(archivo_id=archivo_id, solicitante_id=solicitante_id)
        with self.repo.reclamar_publicador(archivo_id=archivo_id) as comprobar:
            servicios = self.servicios_factory()
            with self._sql(servicios, sesion, comprobar) as (actual, intento):
                self._validar_claves(actual, intento)
                if actual.estado == EstadoSesion.CONFIRMED:
                    raise EstadoIncompatible("No cancelar un archivo confirmado")
                trabajo, _ = TrabajoMantenimiento.objects.using(self.repo.using).get_or_create(
                    sesion_id=actual.pk)
                if not trabajo.cancelar and actual.estado == EstadoSesion.PENDING:
                    trabajo.cancelar = True
                    trabajo.proximo_intento = timezone.now()
                    trabajo.actualizado_en = timezone.now()
                    trabajo.save(using=self.repo.using)
                    self.auditoria(sesion=actual, accion="CANCELACION_SOLICITADA",
                                   motivo="USUARIO", using=self.repo.using)
                if actual.estado == EstadoSesion.PENDING and intento is None:
                    self._finalizar(actual, EstadoSesion.CANCELED)
        self.procesar(sesion.pk)
        sesion.refresh_from_db(using=self.repo.using)
        return {"estado": sesion.estado,
                "pendiente_reconciliacion": sesion.estado == EstadoSesion.PENDING}

    def _guardar_pendiente(self, sesion_id, causa, *, proximo=None):
        # Solo diario, sin adquirir luego cuota/sesión. También sirve si no pudo
        # adquirirse el reclamo o si se perdió la conexión que lo mantenía.
        with transaction.atomic(using=self.repo.using, durable=True):
            trabajo = TrabajoMantenimiento.objects.using(self.repo.using).select_for_update().get(
                sesion_id=sesion_id)
            trabajo.fallos_consecutivos += int(causa != "URL_VIGENTE")
            trabajo.estado = (EstadoMantenimiento.RECONCILE if causa in (
                "COPY_AMBIGUO", "REFERENCIADO", "RECUPERACION", "INTEGRIDAD")
                else EstadoMantenimiento.PENDING if causa == "URL_VIGENTE"
                else EstadoMantenimiento.RETRY)
            trabajo.causa = causa
            trabajo.proximo_intento = proximo or timezone.now() + timedelta(
                seconds=self.politica.espera(trabajo.fallos_consecutivos))
            trabajo.actualizado_en = timezone.now()
            trabajo.save(using=self.repo.using)

    def _borrar_y_verificar(self, cliente, clave, comprobar):
        comprobar()
        try:
            cliente.borrar_tecnico(clave)
        except ErrorS3:
            # Un timeout es ambiguo: HEAD puede demostrar ausencia, no éxito
            # por el mero código de DELETE. 403 nunca equivale a 404.
            comprobar()
            try:
                cliente.consultar(clave)
            except ErrorS3 as error:
                if error.tipo == "ausente":
                    return
                raise
            raise ErrorS3()
        comprobar()
        try:
            cliente.consultar(clave)
        except ErrorS3 as error:
            if error.tipo == "ausente":
                return
            raise
        raise ErrorS3()  # Objeto reaparecido; conservar pendiente.

    def _procesar_reclamado(self, servicios, sesion, comprobar):
        with self._sql(servicios, sesion, comprobar) as (actual, intento):
            self._validar_claves(actual, intento)
            trabajo = TrabajoMantenimiento.objects.using(self.repo.using).select_for_update().get(
                sesion_id=actual.pk)
            if trabajo.proximo_intento > timezone.now():
                return "DIFERIDO"
            trabajo.intentos += 1
            trabajo.estado = EstadoMantenimiento.RETRY
            trabajo.causa = "ERROR"
            trabajo.proximo_intento = timezone.now() + timedelta(seconds=self.politica.reintento_segundos)
            trabajo.actualizado_en = timezone.now()
            trabajo.save(using=self.repo.using)
        # El intento y su reejecución ya son durables antes de cualquier S3.
        with self._sql(servicios, sesion, comprobar) as (actual, intento):
            trabajo = TrabajoMantenimiento.objects.using(self.repo.using).select_for_update().get(
                sesion_id=actual.pk)
            if actual.estado == EstadoSesion.PENDING:
                vencida = actual.expira_en <= timezone.now()
                if intento is not None:
                    if intento.estado != EstadoPublicacion.PREPARED:
                        raise IntegridadCarga("Publicación y sesión incompatibles")
                    self._inspeccionar(servicios, actual, intento.clave_final, exige_copia=True)
                    if not trabajo.cancelar and not vencida:
                        if self.recuperador is None:
                            raise PendienteMantenimiento("RECUPERACION")
                        return "RECUPERAR"
                    self.repo.abandonar_publicacion(archivo_id=actual.archivo_id,
                                                   solicitante_id=actual.solicitante_id)
                    intento.refresh_from_db(using=self.repo.using)
                if trabajo.cancelar or vencida:
                    self._finalizar(actual, EstadoSesion.CANCELED if trabajo.cancelar else EstadoSesion.EXPIRED)
                else:
                    raise PendienteMantenimiento("URL_VIGENTE", proximo=actual.expira_en)
            if actual.estado == EstadoSesion.CONFIRMED:
                if intento is None or intento.estado != EstadoPublicacion.PUBLISHED:
                    raise IntegridadCarga("Confirmación sin publicación coherente")
            elif actual.estado not in (EstadoSesion.CANCELED, EstadoSesion.EXPIRED):
                raise IntegridadCarga("Estado desconocido")
            elif intento is not None and intento.estado not in (
                    EstadoPublicacion.ABANDONED, EstadoPublicacion.CLEANED):
                raise IntegridadCarga("Intento terminal sin reconciliar")
            sesion = actual
        # Transición lógica confirmada aunque todavía no se pueda eliminar.
        seguro_desde = sesion.expira_en + timedelta(seconds=self.politica.margen_segundos)
        if timezone.now() < seguro_desde:
            raise PendienteMantenimiento("URL_VIGENTE", proximo=seguro_desde)
        with self._sql(servicios, sesion, comprobar) as (actual, intento):
            claves = [actual.clave_temporal]
            if actual.estado != EstadoSesion.CONFIRMED and intento is not None:
                claves.append(intento.clave_final)
            for clave in claves:
                self._inspeccionar(servicios, actual, clave, exige_copia=intento is not None)
        cliente = self.cliente_factory()
        try:
            for clave in claves:
                self._borrar_y_verificar(cliente, clave, comprobar)
            # Otra observación conjunta antes de registrar ausencia; nunca
            # promete que un PUT ya iniciado no pueda terminar después.
            for clave in claves:
                comprobar()
                try:
                    cliente.consultar(clave)
                except ErrorS3 as error:
                    if error.tipo != "ausente":
                        raise
                else:
                    raise ErrorS3()
            with self._sql(servicios, sesion, comprobar) as (actual, intento):
                if actual.estado != sesion.estado:
                    raise IntegridadCarga("El estado cambió durante el borrado")
                for clave in claves:
                    self._inspeccionar(servicios, actual, clave, exige_copia=intento is not None)
                trabajo = TrabajoMantenimiento.objects.using(self.repo.using).select_for_update().get(
                    sesion_id=actual.pk)
                if actual.estado != EstadoSesion.CONFIRMED and intento is not None:
                    self.repo.marcar_limpiado(archivo_id=actual.archivo_id,
                                             solicitante_id=actual.solicitante_id)
                if trabajo.verificado_en is None or trabajo.fallos_consecutivos:
                    self.auditoria(sesion=actual, accion="LIMPIEZA_VERIFICADA",
                                   motivo="MANTENIMIENTO", using=self.repo.using)
                trabajo.estado = EstadoMantenimiento.VERIFIED
                trabajo.causa = ""
                trabajo.fallos_consecutivos = 0
                trabajo.verificado_en = timezone.now()
                trabajo.proximo_intento = timezone.now() + timedelta(seconds=self.politica.barrido_segundos)
                trabajo.actualizado_en = timezone.now()
                trabajo.save(using=self.repo.using)
            return "VERIFICADO"
        finally:
            cliente.cerrar()

    def procesar(self, sesion_id):
        self._fuera_sql()
        sesion = SesionCarga.objects.using(self.repo.using).get(pk=sesion_id)
        reclamado = False
        try:
            with self.repo.reclamar_publicador(archivo_id=sesion.archivo_id) as comprobar:
                reclamado = True
                resultado = self._procesar_reclamado(self.servicios_factory(), sesion, comprobar)
            if resultado == "RECUPERAR":
                # El finalizador vuelve a tomar el reclamo y reautoriza. Su modo
                # solo_recuperar rechaza una sesión sin ledger antes de S3.
                self.recuperador(solicitante_id=sesion.solicitante_id, archivo_id=sesion.archivo_id)
                self._guardar_pendiente(sesion.pk, "URL_VIGENTE", proximo=max(
                    timezone.now(), sesion.expira_en + timedelta(seconds=self.politica.margen_segundos)))
                return "RECUPERADO"
            return resultado
        except PendienteMantenimiento as error:
            self._guardar_pendiente(sesion.pk, error.causa, proximo=error.proximo)
            return error.causa
        except Exception as error:
            if isinstance(error, ErrorS3):
                causa = "S3"
            elif isinstance(error, DatabaseError):
                causa = "SQL"
            elif isinstance(error, (IntegridadCarga, EstadoIncompatible, ValueError, TypeError)):
                causa = "INTEGRIDAD"
            elif isinstance(error, ErrorCarga):
                causa = "DEPENDENCIA" if reclamado else "OCUPADO"
            else:
                causa = "ERROR"
            self._guardar_pendiente(sesion.pk, causa)
            return causa

    def metricas(self):
        ahora = timezone.now()
        sesiones = SesionCarga.objects.using(self.repo.using)
        trabajos = TrabajoMantenimiento.objects.using(self.repo.using)
        return {
            "pendientes_vencidas": sesiones.filter(estado=EstadoSesion.PENDING, expira_en__lte=ahora).count(),
            "bytes_reservados_efectivos": sesiones.filter(estado=EstadoSesion.PENDING,
                expira_en__gt=ahora).aggregate(n=Sum("tamano_bytes"))["n"] or 0,
            "temporales_pendientes": trabajos.exclude(estado=EstadoMantenimiento.VERIFIED).count(),
            "prepared_antiguos": IntentoPublicacion.objects.using(self.repo.using).filter(
                estado=EstadoPublicacion.PREPARED, creado_en__lte=ahora - timedelta(
                    seconds=self.politica.preparado_antiguo_segundos)).count(),
            "errores_dependencia": trabajos.filter(causa="DEPENDENCIA").count(),
        }

    def ejecutar(self):
        self._fuera_sql()
        reconstruidos = self.reconstruir()
        candidatos = list(TrabajoMantenimiento.objects.using(self.repo.using).filter(
            proximo_intento__lte=timezone.now()).order_by("proximo_intento", "sesion_id")
            .values_list("sesion_id", flat=True)[:self.politica.lote])
        resultados = {}
        for sesion_id in candidatos:
            resultado = self.procesar(sesion_id)
            resultados[resultado] = resultados.get(resultado, 0) + 1
        return {"reconstruidos": reconstruidos, "procesados": len(candidatos),
                "resultados": resultados, "metricas": self.metricas()}
