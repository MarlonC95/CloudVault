const MESES_ABREVIADOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

const MS_POR_MINUTO = 60 * 1000
const MS_POR_HORA = 60 * MS_POR_MINUTO

/** Convierte una fecha ISO en un texto corto como "02 Sep 2026". */
export function formatearFechaCorta(fechaIso: string): string {
  const fecha = new Date(fechaIso)
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${dia} ${MESES_ABREVIADOS[fecha.getMonth()]} ${fecha.getFullYear()}`
}

function formatearHora(fecha: Date): string {
  const horas = String(fecha.getHours()).padStart(2, '0')
  const minutos = String(fecha.getMinutes()).padStart(2, '0')
  return `${horas}:${minutos}`
}

function esMismoDia(fechaA: Date, fechaB: Date): boolean {
  return fechaA.toDateString() === fechaB.toDateString()
}

/**
 * Convierte una fecha ISO (UTC) en lenguaje cercano, como pide el contrato (sección 0.6):
 * "Justo ahora", "Hace 2 horas", "Ayer 18:30" o "28 Ago 2026".
 */
export function formatearFechaRelativa(fechaIso: string): string {
  const fecha = new Date(fechaIso)
  const ahora = new Date()
  const diferenciaMs = ahora.getTime() - fecha.getTime()

  if (diferenciaMs < MS_POR_MINUTO) return 'Justo ahora'
  if (diferenciaMs < MS_POR_HORA) {
    const minutos = Math.floor(diferenciaMs / MS_POR_MINUTO)
    return `Hace ${minutos} ${minutos === 1 ? 'minuto' : 'minutos'}`
  }
  if (esMismoDia(fecha, ahora)) {
    const horas = Math.floor(diferenciaMs / MS_POR_HORA)
    return `Hace ${horas} ${horas === 1 ? 'hora' : 'horas'}`
  }

  const ayer = new Date(ahora)
  ayer.setDate(ahora.getDate() - 1)
  if (esMismoDia(fecha, ayer)) return `Ayer ${formatearHora(fecha)}`

  return formatearFechaCorta(fechaIso)
}