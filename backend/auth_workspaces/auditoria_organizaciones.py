"""Lectura auditada sobre logs_auditoria existente; sin nuevas persistencias."""

from dataclasses import dataclass

from django.db import DEFAULT_DB_ALIAS, transaction
from rest_framework.exceptions import ValidationError

from .contratos_auditoria import AuditoriaNoDisponible, FiltrosAuditoria, fecha_utc, proyectar_evento
from .models import LogAuditoria
from .permisos_administracion import AccionOrganizacion, autorizar_organizacion


@dataclass(frozen=True)
class PaginaAuditoria:
    count: int
    results: list[dict]
    filtros: FiltrosAuditoria


def consultar_auditoria_organizacion(usuario, organizacion_id, filtros):
    """Owner vigente, lectura acotada y evento obligatorio en el mismo alias.

    Las pruebas aisladas sustituyen el contexto transaccional y el repositorio;
    no demuestran commit/rollback/concurrencia PostgreSQL ni autorizan usar BD.
    """
    with transaction.atomic(using=DEFAULT_DB_ALIAS):
        ambito = autorizar_organizacion(usuario, organizacion_id, AccionOrganizacion.LEER_AUDITORIA)
        repositorio = LogAuditoria.objects.using(DEFAULT_DB_ALIAS)
        consulta = repositorio.filter(
            organizacion_id=ambito.organizacion_id,
            fecha_evento__gte=filtros.desde,
            fecha_evento__lt=filtros.fin_lectura,
        )
        if filtros.usuario_id is not None:
            consulta = consulta.filter(usuario_id=filtros.usuario_id)
        if filtros.accion is not None:
            consulta = consulta.filter(accion=filtros.accion)
        consulta = consulta.order_by("-fecha_evento", "-id")
        count = consulta.count()
        ultima = max(1, (count + filtros.page_size - 1) // filtros.page_size)
        if filtros.page > ultima:
            raise ValidationError({"page": ["La página solicitada no existe."]})
        inicio = (filtros.page - 1) * filtros.page_size
        filas = consulta[inicio:inicio + filtros.page_size].values(
            "id", "organizacion_id", "usuario_id", "accion", "fecha_evento", "detalles",
        )
        resultados = [proyectar_evento(fila) for fila in filas]
        if any(fila["organizacion_id"] != str(ambito.organizacion_id) for fila in resultados):
            raise AuditoriaNoDisponible()
        detalles = {
            "version": 1, "operacion": "AUDITORIA_ORGANIZACION",
            "desde": fecha_utc(filtros.desde), "hasta": fecha_utc(filtros.hasta),
            "fecha_corte": fecha_utc(filtros.corte),
            "pagina": filtros.page, "page_size": filtros.page_size,
            "filtro_accion": filtros.accion is not None,
        }
        if filtros.usuario_id is not None:
            detalles["usuario_filtro_id"] = str(filtros.usuario_id)
        # Nunca copiar cuerpo, IP o valor libre del filtro de acción al evento.
        repositorio.create(
            usuario_id=usuario.pk, organizacion_id=ambito.organizacion_id,
            accion="ADMIN_DATA_ACCESSED", fecha_evento=filtros.corte, detalles=detalles,
        )
        return PaginaAuditoria(count, resultados, filtros)
