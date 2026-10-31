"""Envío lógico coordinado. La cuota pertenece exclusivamente al trigger SQL."""

from contextlib import contextmanager
from uuid import UUID, uuid4

from django.db import DatabaseError
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError


class ErrorPapelera(APIException):
    def __init__(self, codigo="SERVICE_UNAVAILABLE", status=503, *, fields=None):
        self.codigo = codigo
        self.status_code = status
        detalle = {"error": {"code": codigo}}
        if fields:
            detalle["error"]["fields"] = fields
        super().__init__(detalle)


def _error_reclamo_ocupado():
    error = ErrorPapelera("SERVICE_UNAVAILABLE", 503)
    error.es_reclamo_ocupado = True
    return error


def identificador(valor):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({"id": ["El identificador no es válido."]}) from None


class ServicioPapelera:
    def __init__(self, *, repositorio=None, reloj=timezone.now, nuevo_id=uuid4):
        if repositorio is None:
            from .repositorio_papelera import RepositorioPapelera
            repositorio = RepositorioPapelera()
        self.repo, self.reloj, self.nuevo_id = repositorio, reloj, nuevo_id

    @contextmanager
    def reclamar(self, archivo_id):
        from almacenamiento.persistencia import ReclamoOcupado
        from almacenamiento.errores import ErrorCarga
        try:
            with self.repo.reclamar(identificador(archivo_id)) as comprobar:
                yield comprobar
        except ReclamoOcupado:
            raise _error_reclamo_ocupado() from None
        except (ErrorCarga, DatabaseError):
            raise ErrorPapelera() from None

    @contextmanager
    def mutacion(self, *, solicitante_id, organizacion_id, archivo_id,
                 comprobar, eliminado=None, envio=False):
        """Siempre relee dentro de cuota; el reclamo externo se conserva hasta terminar."""
        actor, org, archivo_id = map(identificador, (solicitante_id, organizacion_id, archivo_id))
        try:
            with self.repo.transaccion(org):
                comprobar()
                nivel = self.repo.nivel(actor, org)
                archivo = self.repo.archivo(archivo_id, org)
                if archivo is None:
                    raise NotFound()
                if envio:
                    from .permisos_papelera import autorizar_envio
                    permisos = self.repo.permisos(actor, archivo) if nivel == 3 else ()
                    autorizar_envio(nivel, permisos)
                elif nivel not in (0, 2, 3):
                    raise PermissionDenied()
                if eliminado is not None and archivo.en_papelera != eliminado:
                    raise NotFound()
                if self.repo.purga_pendiente(archivo):
                    raise ErrorPapelera("RESOURCE_BUSY", 409)
                yield archivo
                comprobar()
        except DatabaseError:
            raise ErrorPapelera() from None

    @contextmanager
    def proteger(self, **datos):
        with self.reclamar(datos["archivo_id"]) as comprobar:
            with self.mutacion(comprobar=comprobar, **datos) as archivo:
                yield archivo

    def enviar(self, *, solicitante_id, organizacion_id, archivo_id):
        with self.proteger(solicitante_id=solicitante_id, organizacion_id=organizacion_id,
                           archivo_id=archivo_id, envio=True) as archivo:
            if archivo.en_papelera:
                # Repetir no reinicia retención, ni repara fechas legadas desconocidas.
                return
            ahora = self.reloj()
            if timezone.is_naive(ahora):
                raise ErrorPapelera()
            self.repo.marcar(archivo, ahora)
            self.repo.auditar(archivo=archivo, actor=identificador(solicitante_id), detalles={
                "version": 1, "operacion_id": str(self.nuevo_id()),
                "generacion_id": str(self.nuevo_id()), "tipo_elemento": "archivo",
                "recurso_id": str(archivo.pk), "fecha_papelera": ahora.isoformat(),
                "origen": "API", "tamano_bytes": archivo.tamano_bytes,
                "carpeta_original_id": str(archivo.carpeta_id) if archivo.carpeta_id else None,
            })
        # No devolver éxito antes del commit del repositorio.

    def restaurar(self, *, solicitante_id, organizacion_id, archivo_id):
        with self.proteger(solicitante_id=solicitante_id, organizacion_id=organizacion_id,
                           archivo_id=archivo_id, envio=True) as archivo:
            ultimo = self.repo.ultimo_evento(archivo)
            if not archivo.en_papelera:
                if ultimo is not None and ultimo.accion == 'PAPELERA_RESTAURADO':
                    return
                raise NotFound()
            if archivo.fecha_papelera is None or timezone.is_naive(archivo.fecha_papelera):
                raise ErrorPapelera()
            ahora = self.reloj()
            if timezone.is_naive(ahora) or archivo.fecha_papelera > ahora:
                raise ErrorPapelera()
            actor = identificador(solicitante_id)
            nivel = self.repo.nivel(actor, identificador(organizacion_id))
            destino = self.repo.destino(archivo, actor, nivel)
            if not self.repo.nombre_disponible(archivo.organizacion_id, destino, archivo.nombre,
                                               excluir_archivo=archivo.pk):
                raise ErrorPapelera('VALIDATION_ERROR', 409, fields={'nombre':['Ya existe un recurso con ese nombre.']})
            limite, usado, reservas = self.repo.capacidad(archivo.organizacion_id, ahora)
            if usado + reservas + archivo.tamano_bytes > limite or (
                    archivo.tamano_bytes == 0 and usado + reservas >= limite):
                raise ErrorPapelera('CUOTA_EXCEDIDA', 409)
            generacion = ultimo.detalles.get('generacion_id') if ultimo and ultimo.accion != 'PAPELERA_RESTAURADO' else None
            if not generacion:
                generacion = str(self.nuevo_id())
                self.repo.evento_restauracion(archivo, actor, generacion, 'PAPELERA_GENERACION_ADOPTADA')
            self.repo.reactivar(archivo, destino)
            self.repo.evento_restauracion(archivo, actor, generacion)

    def purgar(self, *, solicitante_id, organizacion_id, archivo_id,
               cliente=None, crear_cliente=None, operacion_lote_id=None):
        """Purgar una generación con intención durable y recuperación por repetición."""
        actor, org, archivo_id = map(identificador, (solicitante_id, organizacion_id, archivo_id))
        return self._purgar(actor=actor, org=org, archivo_id=archivo_id,
                            cliente=cliente, crear_cliente=crear_cliente,
                            operacion_lote_id=operacion_lote_id)

    def purgar_automaticamente(self, *, candidato, cliente=None, crear_cliente=None):
        """Procesa una selección interna y vuelve a validar su instantánea bajo reclamo."""
        org, archivo_id = map(identificador, (candidato.organizacion_id, candidato.archivo_id))
        return self._purgar(actor=None, org=org, archivo_id=archivo_id,
                            cliente=cliente, crear_cliente=crear_cliente,
                            candidato=candidato)

    def _purgar(self, *, actor, org, archivo_id, cliente, crear_cliente, candidato=None,
                operacion_lote_id=None):
        with self.reclamar(archivo_id) as comprobar:
            intencion = None
            intencion_confirmada = False
            try:
                with self.repo.transaccion(org):
                    comprobar()
                    if candidato is None:
                        nivel = self.repo.nivel(actor, org)
                        if nivel != 0:
                            raise PermissionDenied()
                    archivo = self.repo.archivo(archivo_id, org)
                    if candidato is not None:
                        if archivo is None or not archivo.en_papelera:
                            raise ErrorPapelera("CANDIDATE_STALE", 409)
                        if candidato.operacion_id:
                            if not self.repo.validar_identidad_candidato(archivo, candidato):
                                raise ErrorPapelera("CANDIDATE_STALE", 409)
                            if not self.repo.reintento_candidato_vencido(archivo, candidato, self.reloj()):
                                raise ErrorPapelera("RETRY_DEFERRED", 409)
                        elif not self.repo.validar_candidato(archivo, candidato, self.reloj()):
                            raise ErrorPapelera("CANDIDATE_STALE", 409)
                    else:
                        if archivo is None:
                            raise NotFound()
                        if not archivo.en_papelera:
                            raise ErrorPapelera("VALIDATION_ERROR", 409)
                        if self.repo.lote_purga_pendiente(
                                org, archivo_id, excluir_operacion=operacion_lote_id):
                            raise ErrorPapelera("RESOURCE_BUSY", 409)
                    intencion = self.repo.generar_o_reutilizar_intencion(
                        archivo, actor, origen="VENCIMIENTO" if candidato is not None and not candidato.operacion_id else "MANUAL")
                    if candidato is not None and candidato.operacion_id:
                        if intencion.get("operacion_id") != candidato.operacion_id:
                            raise ErrorPapelera("CANDIDATE_STALE", 409)
                    if self.repo.referencia_incompatible(archivo, intencion["clave_s3"]):
                        if candidato is not None:
                            raise ErrorPapelera("PURGE_INCOMPATIBLE", 409)
                        raise ErrorPapelera()
                    if archivo.clave_s3 != intencion["clave_s3"]:
                        if candidato is not None:
                            raise ErrorPapelera("PURGE_INCOMPATIBLE", 409)
                        raise ErrorPapelera()
                intencion_confirmada = True
            except (NotFound, PermissionDenied, ValidationError, ErrorPapelera):
                raise
            except Exception:
                if intencion_confirmada:
                    self._registrar_reintento(org, actor, archivo_id, intencion,
                                              "AUSENCIA_NO_CONFIRMADA")
                raise ErrorPapelera() from None

            creado_aqui = cliente is None
            bytes_eliminados = 0
            try:
                if cliente is None:
                    if not callable(crear_cliente):
                        raise ErrorPapelera()
                    cliente = crear_cliente()
                comprobar()
                bytes_eliminados = cliente.borrar_fisico_verificado(intencion["clave_s3"]) or 0
                comprobar()
            except Exception as exc:
                from almacenamiento.s3 import ErrorS3
                motivo = "S3" if isinstance(exc, ErrorS3) else "AUSENCIA_NO_CONFIRMADA"
                codigo = "SERVICE_UNAVAILABLE"
                estado = 503
                if isinstance(exc, ErrorS3) and exc.tipo == "incompatible":
                    motivo = "INCOMPATIBLE"
                    if candidato is not None:
                        codigo, estado = "PURGE_INCOMPATIBLE", 409
                self._registrar_reintento(org, actor, archivo_id, intencion, motivo,
                                          bytes_fisicos_confirmados=bytes_eliminados)
                if creado_aqui and cliente is not None:
                    try:
                        cliente.cerrar()
                    except Exception:
                        pass
                raise ErrorPapelera(codigo, estado) from None

            try:
                with self.repo.transaccion(org):
                    comprobar()
                    archivo = self.repo.archivo(archivo_id, org)
                    if archivo is None:
                        raise ErrorPapelera()
                    self.repo.cerrar_purga(archivo, actor, intencion,
                                           bytes_fisicos_purgados=bytes_eliminados)
                    comprobar()
            except Exception:
                self._registrar_reintento(org, actor, archivo_id, intencion, "CIERRE",
                                          bytes_fisicos_confirmados=bytes_eliminados)
                raise ErrorPapelera() from None
            finally:
                if creado_aqui and cliente is not None:
                    try:
                        cliente.cerrar()
                    except Exception:
                        pass
            return bytes_eliminados

    def _registrar_reintento(self, org, actor, archivo_id, intencion, motivo,
                             *, bytes_fisicos_confirmados=0):
        if not intencion:
            return
        try:
            with self.repo.transaccion(org):
                archivo = self.repo.archivo(archivo_id, org)
                if archivo is not None:
                    self.repo.auditar_reintento_purga(archivo, actor, intencion, motivo,
                                                       ahora=self.reloj(),
                                                       bytes_fisicos_confirmados=bytes_fisicos_confirmados)
        except Exception:
            # La intención confirmada permanece como evidencia recuperable.
            pass
