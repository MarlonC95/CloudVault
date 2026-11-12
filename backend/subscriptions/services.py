"""Proyección pública de planes y utilidades de formato del contrato.

La tabla ``planes`` solo guarda ``nombre``, ``precio`` y ``limite_almacenamiento_bytes``.
El catálogo visible (código público, características y ``es_popular``) se deriva en
código a partir del id entero del seed, sin inventar columnas.
"""

import calendar
import re
import secrets
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from common.formatting import bytes_legibles as _bytes_legibles

# El seed fija los ids 1-3; su código público es estable y no es una columna.
CODIGOS_PUBLICOS = {1: "gratuito", 2: "pro", 3: "empresarial"}
IDS_PUBLICOS = {codigo: plan_id for plan_id, codigo in CODIGOS_PUBLICOS.items()}

# Características y popularidad en código (el SQL no las define).
CATALOGO = {
    "gratuito": {
        "es_popular": False,
        "caracteristicas": [
            "15 GB almacenamiento",
            "1 Usuario",
            "Cifrado estándar",
            "Soporte por comunidad",
        ],
    },
    "pro": {
        "es_popular": True,
        "caracteristicas": [
            "100 GB almacenamiento",
            "Hasta 5 Usuarios",
            "Cifrado de extremo a extremo",
            "Versionado de archivos",
            "Soporte 24/7",
        ],
    },
    "empresarial": {
        "es_popular": False,
        "caracteristicas": [
            "1 TB almacenamiento",
            "Usuarios ilimitados",
            "Logs de auditoría avanzada",
            "API dedicada",
            "SLA del 99.9%",
        ],
    },
}

_FACTOR_ANUAL = Decimal("0.8")
_MESES_ANUAL = 12


def id_publico(plan_id):
    """Código público del plan; ids fuera del seed conservan un código estable."""
    return CODIGOS_PUBLICOS.get(plan_id, str(plan_id))


def plan_id_desde_codigo(codigo):
    """Id entero del seed a partir del código público; ``None`` si no existe."""
    if isinstance(codigo, bool):
        return None
    if isinstance(codigo, int):
        return codigo if codigo in CODIGOS_PUBLICOS else None
    if isinstance(codigo, str):
        limpio = codigo.strip()
        if limpio in IDS_PUBLICOS:
            return IDS_PUBLICOS[limpio]
        if limpio.isdigit():
            entero = int(limpio)
            return entero if entero in CODIGOS_PUBLICOS else None
    return None


def nombre_mostrado(nombre):
    """Nombre comercial: parte previa a ' / ' ('Pro PaaS / Premium' -> 'Pro PaaS')."""
    return nombre.split(" / ")[0].strip()


def numero(valor):
    """Serializa ``Decimal`` como entero si no tiene decimales (29, no 29.00)."""
    if valor is None:
        return None
    try:
        decimal = Decimal(valor)
    except (InvalidOperation, TypeError):
        return valor
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def precio_anual(precio):
    """Precio anual = round(precio * 12 * 0.8)."""
    if precio is None:
        return None
    return int(round(Decimal(precio) * _MESES_ANUAL * _FACTOR_ANUAL))


def bytes_legibles(valor):
    """Tamaño legible base 1024 (contrato §0.6)."""
    if valor is None:
        return None
    return _bytes_legibles(valor)


def fecha_iso(valor):
    if valor is None:
        return None
    return valor.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def intervalo_a_cliente(intervalo):
    """Vocabulario del cliente: ``MONTHLY``/``YEARLY`` -> ``mensual``/``anual``."""
    return {"MONTHLY": "mensual", "YEARLY": "anual"}.get(intervalo, intervalo)


def intervalo_desde_cliente(tipo):
    """``mensual``/``anual`` -> ``MONTHLY``/``YEARLY``; ``None`` si es inválido."""
    return {"mensual": "MONTHLY", "anual": "YEARLY"}.get(tipo)


def sumar_meses(valor, meses):
    """Suma meses respetando el desbordamiento de mes (sin dependencias externas)."""
    total = valor.month - 1 + meses
    anio = valor.year + total // 12
    mes = total % 12 + 1
    dia = min(valor.day, calendar.monthrange(anio, mes)[1])
    return valor.replace(year=anio, month=mes, day=dia)


def plan_publico(plan):
    """Representación de un plan para el catálogo §10.1."""
    codigo = id_publico(plan.id)
    meta = CATALOGO.get(codigo, {"es_popular": False, "caracteristicas": []})
    return {
        "id": codigo,
        "nombre": nombre_mostrado(plan.nombre),
        "precio_mensual": numero(plan.precio),
        "precio_anual": precio_anual(plan.precio),
        "almacenamiento_bytes": plan.limite_almacenamiento_bytes,
        "almacenamiento_legible": bytes_legibles(plan.limite_almacenamiento_bytes),
        "es_popular": meta["es_popular"],
        "caracteristicas": meta["caracteristicas"],
    }


def bloque_almacenamiento(usado, cuota):
    """Bloque de consumo usado por §10.2."""
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


def token_aleatorio():
    """Referencia de pago simulado."""
    return secrets.token_hex(8)


_ESTADO_PAGO_A_CLIENTE = {"COMPLETED": "pagada"}


def factura_publica(pago):
    """Representación de un pago del historial (§10.4)."""
    suscripcion = pago.suscripcion
    periodo_inicio = suscripcion.periodo_inicio if suscripcion else None
    periodo_fin = suscripcion.periodo_fin if suscripcion else None
    referencia = f"fac-{pago.fecha_pago.year}-{pago.fecha_pago.month:02d}"
    return {
        "id": referencia,
        "monto": numero(pago.monto),
        "moneda": "USD",
        "estado": _ESTADO_PAGO_A_CLIENTE.get(pago.estado, pago.estado.lower()),
        "periodo_inicio": fecha_iso(periodo_inicio),
        "periodo_fin": fecha_iso(periodo_fin),
        "url_pdf": f"https://cloudvault.app/facturas/{referencia}.pdf",
    }


# --- Tarjetas de pago simulado ---------------------------------------------

MAX_TARJETAS = 2
_TIPOS_TARJETA = {"credito": "CREDITO", "debito": "DEBITO"}
_VIGENCIA_MAXIMA_ANIOS = 20


def luhn_valido(numero):
    """Dígito verificador de Luhn (el que usan todas las tarjetas reales)."""
    total = 0
    for posicion, digito in enumerate(reversed(numero)):
        valor = int(digito)
        if posicion % 2:
            valor = valor * 2 - 9 if valor > 4 else valor * 2
        total += valor
    return total % 10 == 0


def marca_tarjeta(numero):
    """Marca por prefijo (IIN); ``otra`` si no es Visa, Mastercard ni Amex."""
    if numero.startswith("4"):
        return "visa"
    if numero[:2] in ("34", "37"):
        return "amex"
    if 51 <= int(numero[:2]) <= 55 or 2221 <= int(numero[:4]) <= 2720:
        return "mastercard"
    return "otra"


def tarjeta_vencida(mes, anio, hoy):
    return (anio, mes) < (hoy.year, hoy.month)


def _entero(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    return None


def validar_tarjeta(datos, hoy, actual=None):
    """Valida el alta (``actual=None``) o la edición parcial de una tarjeta.

    Devuelve ``(limpio, errores)``. ``limpio`` solo contiene columnas guardables:
    del número quedan la marca y los 4 últimos dígitos; el CVV solo se comprueba.
    """
    limpio, errores = {}, {}

    def presente(campo):
        return actual is None or campo in datos

    if presente("titular"):
        titular = " ".join(str(datos.get("titular") or "").split())
        if 2 <= len(titular) <= 100:
            limpio["titular"] = titular
        else:
            errores["titular"] = ["Indica el nombre del titular como aparece en la tarjeta."]

    if presente("tipo"):
        tipo = _TIPOS_TARJETA.get(datos.get("tipo"))
        if tipo:
            limpio["tipo"] = tipo
        else:
            errores["tipo"] = ["El tipo debe ser 'credito' o 'debito'."]

    if presente("numero") or presente("cvv"):
        numero = re.sub(r"[\s-]", "", str(datos.get("numero") or ""))
        marca = None
        if numero.isdigit() and 13 <= len(numero) <= 19 and luhn_valido(numero):
            marca = marca_tarjeta(numero)
            limpio["marca"] = marca
            limpio["ultimos4"] = numero[-4:]
        else:
            errores["numero"] = ["El número de tarjeta no es válido."]
        cvv = str(datos.get("cvv") or "")
        largos = (4,) if marca == "amex" else (3,) if marca else (3, 4)
        if not (cvv.isdigit() and len(cvv) in largos):
            errores["cvv"] = ["El CVV no es válido."]

    if presente("mes_expiracion") or presente("anio_expiracion"):
        mes = _entero(datos.get("mes_expiracion", getattr(actual, "mes_expiracion", None)))
        anio = _entero(datos.get("anio_expiracion", getattr(actual, "anio_expiracion", None)))
        if mes is None or not 1 <= mes <= 12:
            errores["mes_expiracion"] = ["El mes de expiración debe estar entre 1 y 12."]
        elif (
            anio is None
            or tarjeta_vencida(mes, anio, hoy)
            or anio > hoy.year + _VIGENCIA_MAXIMA_ANIOS
        ):
            errores["anio_expiracion"] = ["La tarjeta está vencida o la fecha no es válida."]
        else:
            limpio["mes_expiracion"] = mes
            limpio["anio_expiracion"] = anio

    return limpio, errores


def tarjeta_publica(tarjeta):
    return {
        "id": str(tarjeta.id),
        "titular": tarjeta.titular,
        "marca": tarjeta.marca,
        "tipo": tarjeta.tipo.lower(),
        "ultimos4": tarjeta.ultimos4,
        "mes_expiracion": tarjeta.mes_expiracion,
        "anio_expiracion": tarjeta.anio_expiracion,
        "predeterminada": tarjeta.predeterminada,
    }
