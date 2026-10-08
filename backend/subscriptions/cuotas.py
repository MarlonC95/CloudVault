"""Lectura de la cuota vigente de una organización.

Contrato interno consumido por otras áreas (Run 4): ``leer_cuota_organizacion``
devuelve ``(limite_bytes, usado_bytes, periodo_fin)`` de la única suscripción
ACTIVE vigente de la organización. Sin ella, falla con un error claro en vez de
inventar una cuota.
"""

from django.db import connections
from django.utils import timezone

# El instante se calcula en Python (no ``CURRENT_TIMESTAMP``, que es el inicio de
# la transacción): así la vigencia es correcta aunque la suscripción se haya
# insertado dentro de la misma transacción.
CONSULTA_CUOTA = """
SELECT p.limite_almacenamiento_bytes, o.almacenamiento_usado_bytes, s.periodo_fin
FROM organizaciones o
JOIN suscripciones s ON s.organizacion_id = o.id
JOIN planes p ON p.id = s.plan_id
WHERE o.id = %s
  AND o.esta_activo
  AND p.esta_activo
  AND s.estado = 'ACTIVE'
  AND s.periodo_inicio <= %s
  AND s.periodo_fin > %s
"""


class SinSuscripcionVigente(Exception):
    """La organización no tiene una suscripción ACTIVE con período utilizable."""

    def __init__(self, organizacion_id=None):
        self.organizacion_id = organizacion_id
        super().__init__(
            "La organización no tiene una suscripción ACTIVE vigente."
        )


def leer_cuota_organizacion(organizacion_id, using="default"):
    """Devuelve ``(limite_bytes, usado_bytes, periodo_fin)`` o lanza el error claro."""
    ahora = timezone.now()
    with connections[using].cursor() as cursor:
        cursor.execute(CONSULTA_CUOTA, [organizacion_id, ahora, ahora])
        filas = cursor.fetchall()
    if len(filas) != 1:
        raise SinSuscripcionVigente(organizacion_id)
    limite_bytes, usado_bytes, periodo_fin = filas[0]
    return limite_bytes, usado_bytes, periodo_fin
