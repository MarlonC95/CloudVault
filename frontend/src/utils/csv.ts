/** Marca invisible al inicio del CSV para que Excel reconozca los acentos (UTF-8). */
const MARCA_UTF8_PARA_EXCEL = String.fromCharCode(0xfeff)

function escaparCeldaCsv(valor: string): string {
  return `"${valor.replace(/"/g, '""')}"`
}

/** Convierte un encabezado y sus filas en un CSV que Excel abre bien (con acentos). */
export function convertirFilasACsv(encabezados: string[], filas: string[][]): string {
  const lineas = [encabezados, ...filas].map((fila) => fila.map(escaparCeldaCsv).join(','))
  return `${MARCA_UTF8_PARA_EXCEL}${lineas.join('\r\n')}`
}