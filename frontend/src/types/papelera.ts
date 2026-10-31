import type { TipoArchivo } from './archivo'

/** Elemento de la papelera con su cuenta regresiva (contrato 8). */
export interface ArchivoEnPapelera {
  id: string
  nombre: string
  tipo: TipoArchivo
  tamano: string
  carpetaId: string | null
  eliminadoEn: string | null
  expiraEn: string | null
  diasRestantes: number
}

/** Raíz de un lote lógico de carpeta, servida por la ruta tipada. */
export interface CarpetaEnPapelera {
  id: string
  nombre: string
  tipoElemento: 'carpeta'
  eliminadoEn: string | null
  expiraEn: string | null
  diasRestantes: number
  cantidadElementos: number
  tamanoBytes: number
  puedePurgar: boolean
}
