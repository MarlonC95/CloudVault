import type { Plan, TipoFacturacion } from '../types/planes'

export function esTipoFacturacion(valor: string | null): valor is TipoFacturacion {
  return valor === 'mensual' || valor === 'anual'
}

/** El backend define el precio anual como el total del año (12 meses con 20% de descuento). */
export function obtenerMontoPlan(plan: Plan, facturacion: TipoFacturacion): number {
  return facturacion === 'anual' ? plan.precioAnual : plan.precioMensual
}

export function calcularAhorroAnual(plan: Plan): number {
  return Math.max(0, plan.precioMensual * 12 - plan.precioAnual)
}

export function describirPeriodo(facturacion: TipoFacturacion): string {
  return facturacion === 'anual' ? 'por año' : 'por mes'
}

export function formatearUsd(monto: number): string {
  return `$${monto.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}