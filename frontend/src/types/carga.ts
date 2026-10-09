/** Resultado del paso 1 de la carga directa (contrato 4.1). */
export interface CargaIniciada {
  archivoId: string
  urlSubida: string
  metodo: string
  encabezados: Record<string, string>
  expiraEn: string
}

/** URL firmada y temporal para descargar o previsualizar un archivo (contrato 5). */
export interface UrlTemporal {
  url: string
  expiraEn: string
  nombre?: string
  tipo?: string
}