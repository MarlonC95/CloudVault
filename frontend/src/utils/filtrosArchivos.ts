export function parsearTamanoAMb(tamano: string): number {
  const coincidencia = tamano.match(/([\d.]+)\s*(KB|MB|GB)/i)
  if (!coincidencia) return 0

  const valor = parseFloat(coincidencia[1])
  const unidad = coincidencia[2].toUpperCase()

  if (unidad === 'GB') return valor * 1024
  if (unidad === 'KB') return valor / 1024
  return valor
}

export type RangoTamano = 'cualquiera' | 'pequeno' | 'mediano' | 'grande'

export function cumpleRangoTamano(tamano: string, rango: RangoTamano): boolean {
  if (rango === 'cualquiera') return true
  const mb = parsearTamanoAMb(tamano)

  if (rango === 'pequeno') return mb < 1
  if (rango === 'mediano') return mb >= 1 && mb < 100
  return mb >= 100
}

export type RangoFecha = 'cualquiera' | 'recientes' | 'este-mes' | 'anteriores'

export function cumpleRangoFecha(fechaModificacion: string, rango: RangoFecha): boolean {
  if (rango === 'cualquiera') return true

  const texto = fechaModificacion.toLowerCase()
  const esReciente = texto.includes('hora') || texto.includes('ayer')
  const esEsteMes = texto.includes('ago') || texto.includes('sep')

  if (rango === 'recientes') return esReciente
  if (rango === 'este-mes') return esEsteMes && !esReciente
  return !esReciente && !esEsteMes
}