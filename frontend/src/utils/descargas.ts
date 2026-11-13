/** Descarga un texto como archivo desde el navegador (por ejemplo, un CSV). */
export function descargarTexto(nombreArchivo: string, contenido: string, tipoMime: string): void {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipoMime }))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}