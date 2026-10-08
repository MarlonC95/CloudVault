const MESES_ABREVIADOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

/** Convierte una fecha ISO en un texto corto como "02 Sep 2026". */
export function formatearFechaCorta(fechaIso: string): string {
  const fecha = new Date(fechaIso)
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${dia} ${MESES_ABREVIADOS[fecha.getMonth()]} ${fecha.getFullYear()}`
}