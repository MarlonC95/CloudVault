import calendar
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation

UNIDADES = ("B", "KB", "MB", "GB", "TB", "PB")


def bytes_legibles(valor):
    """Texto legible de un tamaño; ``None`` se muestra como ilimitado (§10.1)."""
    if valor is None:
        return "Ilimitado"
    tamano = float(valor)
    if tamano < 1024:
        return f"{int(tamano)} B"
    for unidad in UNIDADES[1:]:
        tamano /= 1024
        if tamano < 1024:
            texto = f"{tamano:.1f}".rstrip("0").rstrip(".")
            return f"{texto} {unidad}"
    return f"{tamano:.1f} {UNIDADES[-1]}"


def numero(valor):
    """Serializa ``Decimal`` como entero cuando no tiene decimales (contrato: 29, no 29.00)."""
    if valor is None:
        return None
    try:
        decimal = Decimal(valor)
    except (InvalidOperation, TypeError):
        return valor
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def fecha_iso(valor):
    if valor is None:
        return None
    return valor.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def sumar_meses(valor, meses):
    """Suma meses respetando el desbordamiento de mes (sin dependencias externas)."""
    total = valor.month - 1 + meses
    anio = valor.year + total // 12
    mes = total % 12 + 1
    dia = min(valor.day, calendar.monthrange(anio, mes)[1])
    return valor.replace(year=anio, month=mes, day=dia)


def plan_publico(plan):
    """Representación de un plan para el catálogo §10.1."""
    return {
        "id": plan.slug,
        "nombre": plan.nombre,
        "precio_mensual": numero(plan.precio_mensual),
        "precio_anual": numero(plan.precio_anual),
        "almacenamiento_bytes": plan.almacenamiento_bytes,
        "almacenamiento_legible": bytes_legibles(plan.almacenamiento_bytes),
        "es_popular": plan.es_popular,
        "caracteristicas": plan.caracteristicas,
    }


def bloque_almacenamiento(usado, cuota):
    """Bloque de consumo usado por §10.2 y §3.11."""
    if cuota:
        porcentaje = int(round(usado / cuota * 100))
        libre = max(cuota - usado, 0)
    else:
        porcentaje = 0
        libre = None
    return {
        "usado_bytes": usado,
        "cuota_bytes": cuota,
        "usado_legible": bytes_legibles(usado),
        "cuota_legible": bytes_legibles(cuota),
        "libre_legible": bytes_legibles(libre),
        "porcentaje_usado": porcentaje,
    }
