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

export interface MiPlan {
  plan: { id: string; nombre: string; tipoFacturacion: TipoFacturacion }
  estado: string
  renuevaEn: string
  porcentajeUsado: number
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