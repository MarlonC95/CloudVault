import { clienteApi } from './clienteApi'
import type { RespuestaApi } from '../types/api'
import type { DatosNuevoEnlace, EnlaceActivo, EnlaceCompartido, RecursoPublico } from '../types/enlaces'

interface EnlaceCompartidoApi {
  id: string
  url_compartida: string
  token: string
  password_protegido: boolean
  permite_descarga: boolean
}

interface EnlaceActivoApi {
  id: string
  nombre_archivo: string
  token: string
  activo: boolean
}

interface RecursoPublicoApi {
  nombre: string
  tipo: string
  tamano_legible: string
  url_descarga: string
  permite_descarga: boolean
  expira_en: string
}

/** POST /enlaces-compartidos/ (contrato 6.1): crea un enlace público con o sin clave. */
export async function crearEnlaceCompartido(datos: DatosNuevoEnlace): Promise<EnlaceCompartido> {
  const respuesta = await clienteApi.post<RespuestaApi<EnlaceCompartidoApi>>('/enlaces-compartidos/', {
    archivo_id: datos.archivoId,
    expira_en: datos.expiraEn,
    password: datos.password ?? null,
    permite_descarga: datos.permiteDescarga,
  })
  const enlace = respuesta.data.data
  return {
    id: enlace.id,
    urlCompartida: enlace.url_compartida,
    token: enlace.token,
    passwordProtegido: enlace.password_protegido,
    permiteDescarga: enlace.permite_descarga,
  }
}

/** GET /enlaces-compartidos/ (contrato 6.2): enlaces activos del usuario. */
export async function listarEnlacesCompartidos(): Promise<EnlaceActivo[]> {
  const respuesta = await clienteApi.get<RespuestaApi<{ results: EnlaceActivoApi[] }>>('/enlaces-compartidos/')
  return respuesta.data.data.results.map((enlace) => ({
    id: enlace.id,
    nombreArchivo: enlace.nombre_archivo,
    token: enlace.token,
    activo: enlace.activo,
  }))
}

/** DELETE /enlaces-compartidos/{id}/ (contrato 6.3): revoca el enlace de forma irreversible. */
export async function revocarEnlaceCompartido(enlaceId: string): Promise<void> {
  await clienteApi.delete(`/enlaces-compartidos/${enlaceId}/`)
}

/** GET /publico/{token}/ (contrato 6.4): acceso público, sin sesión. Pide `password` si el enlace la tiene. */
export async function obtenerRecursoPublico(token: string, password?: string): Promise<RecursoPublico> {
  const respuesta = await clienteApi.get<RespuestaApi<RecursoPublicoApi>>(`/publico/${token}/`, {
    params: password ? { password } : undefined,
  })
  const recurso = respuesta.data.data
  return {
    nombre: recurso.nombre,
    tipo: recurso.tipo,
    tamanoLegible: recurso.tamano_legible,
    urlDescarga: recurso.url_descarga,
    permiteDescarga: recurso.permite_descarga,
    expiraEn: recurso.expira_en,
  }
}