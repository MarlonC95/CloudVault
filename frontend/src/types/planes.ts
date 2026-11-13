export type TipoFacturacion = 'mensual' | 'anual'

export interface Plan {
  id: string
  nombre: string
  precioMensual: number
  precioAnual: number
  almacenamientoLegible: string
  esPopular: boolean
  caracteristicas: string[]
}

export interface AlmacenamientoMiPlan {
  usadoBytes: number
  cuotaBytes: number | null
  usadoLegible: string
  cuotaLegible: string
  libreLegible: string
  porcentajeUsado: number
}

export interface MiPlan {
  plan: { id: string; nombre: string; tipoFacturacion: TipoFacturacion }
  estado: string
  renuevaEn: string
  almacenamiento: AlmacenamientoMiPlan
}

export interface Factura {
  id: string
  monto: number
  moneda: string
  estado: string
  periodoInicio: string
  periodoFin: string
  urlPdf: string
}
export type TipoTarjeta = 'credito' | 'debito'

/** Tarjeta guardada para el pago simulado: nunca incluye el número completo ni el CVV. */
export interface Tarjeta {
  id: string
  titular: string
  marca: string
  tipo: TipoTarjeta
  ultimos4: string
  mesExpiracion: number
  anioExpiracion: number
  predeterminada: boolean
}

/** Datos del formulario; `numero` y `cvv` solo viajan al backend para validarse. */
export interface DatosTarjeta {
  titular: string
  numero: string
  cvv: string
  mesExpiracion: number
  anioExpiracion: number
  tipo: TipoTarjeta
}

/** Respuesta de POST /mi-plan/suscribir/ con el plan ya aplicado. */
export interface ResultadoSuscripcion {
  plan: { id: string; nombre: string; tipoFacturacion: TipoFacturacion }
  estado: string
  renuevaEn: string
}
