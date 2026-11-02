import { clienteApi } from './clienteApi'
import { obtenerSesion, renovarAccessToken } from './authService'
import type { RespuestaApi } from '../types/api'
import type { UrlTemporal } from '../types/carga'
import type {
  ContenidoCarpeta,
  DatosEnlace,
  ElementoCompartido,
  EnlaceCompartido,
  PermisoUsuario,
  RecursoCompartible,
  RecursoPublico,
  RolCompartido,
  TipoRecurso,
} from '../types/enlaces'

interface EnlaceApi {
  id: string
  token: string
  rol: RolCompartido
  permite_descarga: boolean
  requiere_password: boolean
  fecha_expiracion: string | null
}

interface PermisoApi {
  id: number
  usuario: { id: string; correo: string; nombre: string }
  tipo_permiso: RolCompartido
  permite_descarga: boolean
  via_enlace: boolean
}

interface CompartidoApi {
  tipo: TipoRecurso
  id: string
  nombre: string
  rol: RolCompartido
  permite_descarga: boolean
  tamano_bytes: number | null
}

interface ContenidoApi {
  carpeta: { id: string; nombre: string; padre_id: string | null }
  rol: RolCompartido
  permite_descarga: boolean
  puede_subir?: boolean
  carpetas: { id: string; nombre: string }[]
  archivos: { id: string; nombre: string; tamano_bytes: number; tipo_mime: string }[]
}

interface PublicoApi {
  tipo: TipoRecurso
  requiere_password: boolean
  id?: string
  nombre?: string
  rol?: RolCompartido
  permite_descarga?: boolean
  unido?: boolean
  puede_subir?: boolean
  tamano_bytes?: number
}

interface UrlPublicaApi {
  url_descarga?: string
  url_vista_previa?: string
  nombre?: string
  tipo?: string
  expira_en: string
}

/** `archivo_id` o `carpeta_id`, según lo que se comparta. */
function campoRecurso(recurso: RecursoCompartible) {
  return recurso.tipo === 'archivo' ? { archivo_id: recurso.id } : { carpeta_id: recurso.id }
}

const mapearEnlace = (e: EnlaceApi): EnlaceCompartido => ({
  id: e.id,
  token: e.token,
  rol: e.rol,
  permiteDescarga: e.permite_descarga,
  requierePassword: e.requiere_password,
  fechaExpiracion: e.fecha_expiracion,
})

const mapearPermiso = (p: PermisoApi): PermisoUsuario => ({
  id: p.id,
  correo: p.usuario.correo,
  nombre: p.usuario.nombre,
  rol: p.tipo_permiso,
  permiteDescarga: p.permite_descarga,
  viaEnlace: p.via_enlace,
})

function mapearContenido(c: ContenidoApi): ContenidoCarpeta & { puedeSubir: boolean } {
  return {
    carpeta: { id: c.carpeta.id, nombre: c.carpeta.nombre, padreId: c.carpeta.padre_id },
    rol: c.rol,
    permiteDescarga: c.permite_descarga,
    puedeSubir: c.puede_subir ?? false,
    carpetas: c.carpetas,
    archivos: c.archivos.map((a) => ({ id: a.id, nombre: a.nombre, tamanoBytes: a.tamano_bytes, tipoMime: a.tipo_mime })),
  }
}

// --- Dueño: enlace y personas ---

/** GET /enlaces-compartidos/?archivo_id|carpeta_id: el enlace del recurso, o `null` si no tiene. */
export async function obtenerEnlace(recurso: RecursoCompartible): Promise<EnlaceCompartido | null> {
  const r = await clienteApi.get<RespuestaApi<EnlaceApi | null>>('/enlaces-compartidos/', { params: campoRecurso(recurso) })
  return r.data.data ? mapearEnlace(r.data.data) : null
}

/** POST /enlaces-compartidos/: crea el enlace o actualiza el existente (uno por recurso). */
export async function guardarEnlace(recurso: RecursoCompartible, datos: DatosEnlace): Promise<EnlaceCompartido> {
  const r = await clienteApi.post<RespuestaApi<EnlaceApi>>('/enlaces-compartidos/', {
    ...campoRecurso(recurso),
    rol: datos.rol,
    permite_descarga: datos.permiteDescarga,
    fecha_expiracion: datos.fechaExpiracion,
    ...(datos.password !== undefined && { password: datos.password }),
  })
  return mapearEnlace(r.data.data)
}

export async function revocarEnlace(enlaceId: string): Promise<void> {
  await clienteApi.delete(`/enlaces-compartidos/${enlaceId}/`)
}

export async function listarPermisos(recurso: RecursoCompartible): Promise<PermisoUsuario[]> {
  const r = await clienteApi.get<RespuestaApi<PermisoApi[]>>('/permisos-recurso/', { params: campoRecurso(recurso) })
  return r.data.data.map(mapearPermiso)
}

export async function compartirConUsuario(
  recurso: RecursoCompartible,
  correo: string,
  rol: RolCompartido,
  permiteDescarga: boolean,
): Promise<PermisoUsuario> {
  const r = await clienteApi.post<RespuestaApi<PermisoApi>>('/permisos-recurso/', {
    ...campoRecurso(recurso),
    correo,
    tipo_permiso: rol,
    permite_descarga: permiteDescarga,
  })
  return mapearPermiso(r.data.data)
}

export async function actualizarPermiso(id: number, rol: RolCompartido, permiteDescarga: boolean): Promise<PermisoUsuario> {
  const r = await clienteApi.patch<RespuestaApi<PermisoApi>>(`/permisos-recurso/${id}/`, {
    tipo_permiso: rol,
    permite_descarga: permiteDescarga,
  })
  return mapearPermiso(r.data.data)
}

export async function quitarPermiso(id: number): Promise<void> {
  await clienteApi.delete(`/permisos-recurso/${id}/`)
}

// --- Invitado con sesión ---

export async function listarCompartidosConmigo(): Promise<ElementoCompartido[]> {
  const r = await clienteApi.get<RespuestaApi<CompartidoApi[]>>('/compartidos-conmigo/')
  return r.data.data.map((c) => ({
    tipo: c.tipo,
    id: c.id,
    nombre: c.nombre,
    rol: c.rol,
    permiteDescarga: c.permite_descarga,
    tamanoBytes: c.tamano_bytes,
  }))
}

export async function obtenerContenidoCompartido(carpetaId: string) {
  const r = await clienteApi.get<RespuestaApi<ContenidoApi>>(`/compartidos-conmigo/carpetas/${carpetaId}/contenido/`)
  return mapearContenido(r.data.data)
}

// --- Enlace público (/s/:token), con o sin sesión ---

const claveShare = (token: string) => `cv-share:${token}`

function cabecerasPublicas(token: string) {
  let share: string | null = null
  try {
    share = sessionStorage.getItem(claveShare(token))
  } catch {
    // sessionStorage bloqueado: el enlace con contraseña pedirá la clave en cada carga.
  }
  return share ? { 'X-Share-Token': share } : {}
}

/**
 * Las rutas públicas tratan un access token vencido como anónimo (no responden 401), así que el
 * reintento de clienteApi no salta: se renueva antes para que el invitado con sesión sea reconocido.
 */
async function prepararSesion() {
  const sesion = obtenerSesion()
  if (sesion && sesion.venceEnMs <= Date.now() + 5000) await renovarAccessToken().catch(() => undefined)
}

async function getPublico<T>(token: string, ruta: string, params?: Record<string, string>): Promise<T> {
  await prepararSesion()
  const r = await clienteApi.get<RespuestaApi<T>>(`/publico/${encodeURIComponent(token)}/${ruta}`, {
    params,
    headers: cabecerasPublicas(token),
  })
  return r.data.data
}

export async function obtenerPublico(token: string): Promise<RecursoPublico> {
  const p = await getPublico<PublicoApi>(token, '')
  return {
    tipo: p.tipo,
    requierePassword: p.requiere_password,
    bloqueado: p.id === undefined,
    id: p.id,
    nombre: p.nombre,
    rol: p.rol,
    permiteDescarga: p.permite_descarga,
    unido: p.unido,
    puedeSubir: p.puede_subir,
    tamanoBytes: p.tamano_bytes,
  }
}

/** POST /publico/{token}/acceso/: valida la contraseña y guarda el share token (15 min) para esta pestaña. */
export async function accederConPassword(token: string, password: string): Promise<void> {
  const r = await clienteApi.post<RespuestaApi<{ share_token: string }>>(
    `/publico/${encodeURIComponent(token)}/acceso/`,
    { password },
  )
  try {
    sessionStorage.setItem(claveShare(token), r.data.data.share_token)
  } catch {
    // Sin sessionStorage no se puede recordar el acceso.
  }
}

export function olvidarAccesoPublico(token: string) {
  try {
    sessionStorage.removeItem(claveShare(token))
  } catch {
    // nada que borrar
  }
}

export async function obtenerContenidoPublico(token: string, carpetaId?: string) {
  return mapearContenido(await getPublico<ContenidoApi>(token, 'contenido/', carpetaId ? { carpeta_id: carpetaId } : undefined))
}

export async function obtenerArchivoPublico(token: string, archivoId: string, accion: 'ver' | 'descargar'): Promise<UrlTemporal> {
  const d = await getPublico<UrlPublicaApi>(token, `archivos/${archivoId}/`, { accion })
  return { url: d.url_descarga ?? d.url_vista_previa ?? '', expiraEn: d.expira_en, nombre: d.nombre, tipo: d.tipo }
}
