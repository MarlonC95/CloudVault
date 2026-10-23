import type { TipoArchivo } from './archivo'

export interface CategoriaAlmacenamiento {
  etiqueta: string
  tamanoLegible: string
  color: string
}

/** Resumen global de almacenamiento (contrato 3.11): alimenta la barra lateral del dashboard. */
export interface ResumenAlmacenamiento {
  usadoBytes: number
  cuotaBytes: number
  usadoLegible: string
  cuotaLegible: string
  libreLegible: string
  porcentajeUsado: number
  cantidadArchivos: number
  cantidadCarpetas: number
  porCategoria: CategoriaAlmacenamiento[]
}

export interface EventoActividad {
  id: string
  accion: string
  descripcion: string
  archivo: string
  creadoEn: string
}

/** Archivo tocado recientemente (contrato 7.2). */
export interface ArchivoReciente {
  id: string
  nombre: string
  tipo: TipoArchivo
  tamano: string
  fechaModificacion: string
}

/** Archivo que otra persona compartió con el usuario (contrato 9). */
export interface ArchivoCompartido {
  id: string
  archivoId: string
  nombre: string
  tipo: TipoArchivo
  tamano: string
  propietario: string
  permiso: string
  fechaModificacion: string
}