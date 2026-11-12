import { clienteApi } from './clienteApi'
import type { RolMiembroEditable } from './organizacionesService'
import { mapearPagina, type PaginaApi, type RespuestaApi } from '../types/api'

export type DecisionInvitacion = 'ACEPTAR' | 'RECHAZAR'

interface InvitacionApi {
  id: string
  organizacion_id: string
  rol: RolMiembroEditable
  fecha_expiracion: string
  organizacion_nombre?: string
  correo_electronico?: string
}

const recibidas = '/organizaciones/invitaciones/'
const raizOrganizacion = (id: string) => `/organizaciones/${encodeURIComponent(id)}/`
const enviadas = (id: string) => `${raizOrganizacion(id)}invitaciones/`

export async function listarInvitaciones(pagina: number, signal: AbortSignal, organizacionId?: string) {
  const ruta = organizacionId ? enviadas(organizacionId) : `${recibidas}recibidas/`
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<InvitacionApi>>>(ruta, {
    params: { page: pagina },
    signal,
  })
  return mapearPagina(respuesta.data.data, (fila) => ({
    id: fila.id,
    rol: fila.rol,
    fechaExpiracion: fila.fecha_expiracion,
    descripcion: (organizacionId ? fila.correo_electronico : fila.organizacion_nombre) ?? '',
  }))
}

export async function enviarInvitacion(organizacionId: string, correoElectronico: string, rol: RolMiembroEditable) {
  await clienteApi.post(`${raizOrganizacion(organizacionId)}miembros/invitar/`, {
    correo_electronico: correoElectronico,
    rol,
  })
}

export async function decidirInvitacion(id: string, decision: DecisionInvitacion) {
  await clienteApi.post(`${recibidas}${encodeURIComponent(id)}/decision/`, { decision })
}

export async function revocarInvitacion(organizacionId: string, id: string) {
  await clienteApi.delete(`${enviadas(organizacionId)}${encodeURIComponent(id)}/`)
}

export async function crearOrganizacionCompartida(id: string, nombre: string) {
  await clienteApi.post('/organizaciones/compartidas/', { id, nombre })
}
