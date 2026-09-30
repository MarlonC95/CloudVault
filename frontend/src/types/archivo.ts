export type TipoArchivo = 'pdf' | 'zip' | 'png' | 'js' | 'xlsx' | 'mp4' | 'docx' | 'otro'

export interface Archivo {
  id: string
  nombre: string
  tipo: TipoArchivo
  fechaModificacion: string
  tamano: string
  propietario: string
  cifrado: boolean
  esNuevo?: boolean
}

export interface Carpeta {
  id: string
  nombre: string
  cantidadArchivos: number
  color: string
  colorFondo: string
}

export interface CargaEnProgreso {
  id: string
  nombreArchivo: string
  tamano: string
  progreso: number
  estado: 'subiendo' | 'en-cola'
}