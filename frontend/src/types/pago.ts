export type MarcaTarjeta = 'visa' | 'mastercard' | 'amex' | 'desconocida'

/** Datos que se escriben en el formulario. Nunca salen del navegador: el pago es simulado. */
export interface DatosTarjeta {
  titular: string
  numero: string
  vencimiento: string
  cvv: string
}

export type CampoTarjeta = keyof DatosTarjeta

export type ErroresTarjeta = Partial<Record<CampoTarjeta, string>>

export type EtapaPago = 'formulario' | 'procesando' | 'aprobado' | 'rechazado'