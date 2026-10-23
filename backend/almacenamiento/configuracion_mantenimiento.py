"""Política propia y composición; no instala SQL ni configura un scheduler."""

from dataclasses import dataclass

from .configuracion_inicio import (
    cliente_firmador, entero_configurado, maximo_publicacion, servicios_compartidos,
    verificador_publicacion,
)
from .contrato import CodigoError
from .errores import ErrorCarga


@dataclass(frozen=True)
class PoliticaMantenimiento:
    margen_segundos: int = 300
    reintento_segundos: int = 60
    reintento_maximo_segundos: int = 3600
    barrido_segundos: int = 3600
    preparado_antiguo_segundos: int = 3600
    lote: int = 100

    def __post_init__(self):
        if (any(type(v) is not int or not 0 < v <= 86400 for v in (
                self.margen_segundos, self.reintento_segundos, self.reintento_maximo_segundos,
                self.barrido_segundos, self.preparado_antiguo_segundos))
                or self.reintento_segundos > self.reintento_maximo_segundos
                or type(self.lote) is not int or not 0 < self.lote <= 1000):
            raise ValueError("Política de mantenimiento inválida")

    def espera(self, fallos):
        return min(self.reintento_maximo_segundos,
                   self.reintento_segundos * (2 ** min(max(fallos - 1, 0), 16)))


def politica_mantenimiento():
    try:
        return PoliticaMantenimiento(**{
            campo: entero_configurado(nombre, defecto) for campo, nombre, defecto in (
                ("margen_segundos", "ALMACENAMIENTO_MARGEN_LIMPIEZA_SEGUNDOS", 300),
                ("reintento_segundos", "ALMACENAMIENTO_REINTENTO_SEGUNDOS", 60),
                ("reintento_maximo_segundos", "ALMACENAMIENTO_REINTENTO_MAXIMO_SEGUNDOS", 3600),
                ("barrido_segundos", "ALMACENAMIENTO_BARRIDO_SEGUNDOS", 3600),
                ("preparado_antiguo_segundos", "ALMACENAMIENTO_PREPARADO_ANTIGUO_SEGUNDOS", 3600),
                ("lote", "ALMACENAMIENTO_MANTENIMIENTO_LOTE", 100),
            )})
    except ValueError:
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None


def crear_servicio_mantenimiento():
    from .confirmacion import ServicioConfirmacionCargas
    from .mantenimiento import ServicioMantenimiento

    def recuperar(*, solicitante_id, archivo_id):
        return ServicioConfirmacionCargas(
            servicios_factory=servicios_compartidos, cliente_factory=cliente_firmador,
            verificador=verificador_publicacion(), maximo_bytes=maximo_publicacion(),
        ).confirmar(solicitante_id=solicitante_id, archivo_id=str(archivo_id),
                    datos={}, solo_recuperar=True)

    return ServicioMantenimiento(servicios_factory=servicios_compartidos,
        cliente_factory=cliente_firmador, recuperador=recuperar, politica=politica_mantenimiento())
