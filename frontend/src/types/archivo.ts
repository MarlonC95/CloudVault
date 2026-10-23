export type TipoArchivo = 'pdf' | 'zip' | 'png' | 'js' | 'xlsx' | 'mp4' | 'docx' | 'otro'

export interface Archivo {
  id: string
  nombre: string
  tipo: TipoArchivo
  fechaModificacion: string
  tamano: string
  tamanoBytes: number
  fechaModificacionIso: string
  propietario: string
  cifrado: boolean
  esNuevo?: boolean
  enPapelera?: boolean
  /** Fecha ISO (UTC) en la que el archivo pasó a la papelera. Solo existe si enPapelera es true. */
  eliminadoEn?: string
  carpetaId: string | null
}

export interface Carpeta {
  id: string
  nombre: string
  color: string
  colorFondo: string
  cantidadArchivos: number
  padreId: string | null
}

export interface CargaEnProgreso {
  id: string
  nombreArchivo: string
  tamano: string
  progreso: number
  estado: 'subiendo' | 'en-cola' | 'completado' | 'error'
  mensajeError?: string
}
