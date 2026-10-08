/** Envoltorio de éxito del contrato (sección 0.2): toda respuesta nueva viene dentro de `data`. */
export interface RespuestaApi<T> {
  data: T
}

/** Paginación tal como la devuelve el backend (sección 0.5). */
export interface PaginaApi<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** Paginación ya traducida al lenguaje del frontend. */
export interface Pagina<T> {
  total: number
  urlSiguiente: string | null
  urlAnterior: string | null
  resultados: T[]
}

export function mapearPagina<Origen, Destino>(
  pagina: PaginaApi<Origen>,
  mapearElemento: (elemento: Origen) => Destino,
): Pagina<Destino> {
  return {
    total: pagina.count,
    urlSiguiente: pagina.next,
    urlAnterior: pagina.previous,
    resultados: pagina.results.map(mapearElemento),
  }
}

/** Respuesta que solo trae un mensaje de confirmación. */
export interface RespuestaMensajeApi {
  mensaje: string
}