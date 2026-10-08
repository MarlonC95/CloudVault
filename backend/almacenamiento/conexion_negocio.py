"""Fábrica del puente propio; consume negocio sin implementar sus modelos."""

import inspect
import os

from django.conf import settings
from django.utils.module_loading import import_string

from .adaptadores import ServiciosCompartidosValidados
from .contrato import CodigoError
from .errores import ErrorCarga


# Los valores son solo nombres de parámetros; no se ejecutan las operaciones
# al verificar la interfaz. Las identidades/resultados se validan en el puente.
PARAMETROS_PROVEEDOR = {
    "resolver_destino": ("solicitante_id", "carpeta_id"),
    "bloquear_cuota": ("organizacion_id",),
    "leer_cuota": ("organizacion_id",),
    "registrar_archivo": ("archivo",),
    "autorizar_descarga": ("solicitante_id", "archivo_id"),
    "inspeccionar_objeto_tecnico": ("sesion_id", "organizacion_id", "clave"),
}


def _validar_llamada(funcion, parametros):
    if (not callable(funcion) or inspect.iscoroutinefunction(funcion)
            or inspect.isasyncgenfunction(funcion)):
        raise ValueError("El proveedor requiere operaciones síncronas")
    inspect.signature(funcion).bind(**{nombre: None for nombre in parametros})


def validar_proveedor(proveedor):
    """Verificar las seis operaciones y alias, sin SQL, S3 ni permisos nuevos.

    Una interfaz válida no acredita esquema, ACL ni coordinación de escritores.
    Esas invariantes se contrastan durante el flujo y la prueba conjunta.
    """
    if getattr(proveedor, "using", None) != "default":
        raise ValueError("El proveedor requiere el alias SQL compartido")
    for nombre, parametros in PARAMETROS_PROVEEDOR.items():
        _validar_llamada(getattr(proveedor, nombre, None), parametros)
    return proveedor


def crear_servicios_almacenamiento():
    """Cargar la fábrica de negocio configurada y envolver el proveedor real.

    ALMACENAMIENTO_SERVICIOS_FACTORY apunta a negocio, nunca a esta función.
    Su constructor debe ser local y sin efectos: las operaciones se invocan
    después, dentro de la coordinación de carga/descarga/mantenimiento.
    """
    fabrica = getattr(settings, "ALMACENAMIENTO_SERVICIOS_FACTORY",
                      os.environ.get("ALMACENAMIENTO_SERVICIOS_FACTORY", ""))
    if not fabrica:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE)
    try:
        funcion = import_string(fabrica) if isinstance(fabrica, str) else fabrica
        if funcion is crear_servicios_almacenamiento:
            raise ValueError("La fábrica de negocio no puede ser el cargador")
        _validar_llamada(funcion, ())
        proveedor = validar_proveedor(funcion())
        return ServiciosCompartidosValidados(proveedor)
    except Exception:
        # No divulgar paths de configuración, mensajes SQL ni credenciales de
        # inicialización. No sustituir una dependencia caída por una fixture.
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None
