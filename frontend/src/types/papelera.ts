import type { TipoArchivo } from './archivo'

/** Elemento de la papelera con su cuenta regresiva (contrato 8). */
export interface ArchivoEnPapelera {
  id: string
  nombre: string
  tipo: TipoArchivo
  tamano: string
  eliminadoEn: string
  expiraEn: string
  diasRestantes: number
}