export type RolCompartido = 'LECTURA' | 'ESCRITURA'
export type TipoRecurso = 'archivo' | 'carpeta'

/** Archivo o carpeta que se comparte; el backend recibe `archivo_id` o `carpeta_id` según el tipo. */
export interface RecursoCompartible {
  tipo: TipoRecurso
  id: string
  nombre: string
}

/** Nivel de acceso tal como lo elige el usuario: "solo ver", "ver y descargar" o "puede subir" (solo carpetas). */
export type NivelAcceso = 'ver' | 'descargar' | 'subir'

export const NIVELES_ACCESO: Record<NivelAcceso, { etiqueta: string; rol: RolCompartido; permiteDescarga: boolean }> = {
  ver: { etiqueta: 'Solo ver', rol: 'LECTURA', permiteDescarga: false },
  descargar: { etiqueta: 'Ver y descargar', rol: 'LECTURA', permiteDescarga: true },
  subir: { etiqueta: 'Editor (puede subir)', rol: 'ESCRITURA', permiteDescarga: true },
}

export function nivelDe(rol: RolCompartido, permiteDescarga: boolean): NivelAcceso {
  return rol === 'ESCRITURA' ? 'subir' : permiteDescarga ? 'descargar' : 'ver'
}

export interface EnlaceCompartido {
  id: string
  token: string
  rol: RolCompartido
  permiteDescarga: boolean
  requierePassword: boolean
  fechaExpiracion: string | null
}

export interface DatosEnlace {
  rol: RolCompartido
  permiteDescarga: boolean
  fechaExpiracion: string | null
  /** `undefined` conserva la contraseña actual; `null` la quita. */
  password?: string | null
}

export interface PermisoUsuario {
  id: number
  correo: string
  nombre: string
  rol: RolCompartido
  permiteDescarga: boolean
  viaEnlace: boolean
}

export interface ElementoCompartido {
  tipo: TipoRecurso
  id: string
  nombre: string
  rol: RolCompartido
  permiteDescarga: boolean
  tamanoBytes: number | null
}

export interface ArchivoDeCarpeta {
  id: string
  nombre: string
  tamanoBytes: number
  tipoMime: string
}

export interface ContenidoCarpeta {
  carpeta: { id: string; nombre: string; padreId: string | null }
  rol: RolCompartido
  permiteDescarga: boolean
  carpetas: { id: string; nombre: string }[]
  archivos: ArchivoDeCarpeta[]
}

/** GET /publico/{token}/. Si `requierePassword` y aún no se verificó, solo llegan `tipo` y `requierePassword`. */
export interface RecursoPublico {
  tipo: TipoRecurso
  requierePassword: boolean
  bloqueado: boolean
  id?: string
  nombre?: string
  rol?: RolCompartido
  permiteDescarga?: boolean
  unido?: boolean
  puedeSubir?: boolean
  tamanoBytes?: number
}
