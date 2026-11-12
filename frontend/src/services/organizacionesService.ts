import { clienteApi } from './clienteApi'
import { mapearPagina, type Pagina, type PaginaApi, type RespuestaApi, type RespuestaMensajeApi } from '../types/api'

type TipoOrganizacion = 'PERSONAL' | 'COMPARTIDO' | null

export interface OrganizacionDisponible { id: string; nombre: string; nivelRol: number; tipo: TipoOrganizacion }
interface OrganizacionApi { id: string; nombre: string; nivel_rol: number; tipo: TipoOrganizacion }

export async function listarOrganizacionesDisponibles(): Promise<OrganizacionDisponible[]> {
  const organizaciones: OrganizacionDisponible[] = []
  for (let page = 1; ; page += 1) {
    const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<OrganizacionApi>>>(
      '/organizaciones/disponibles/', { params: { page, page_size: 100 } })
    const pagina = respuesta.data.data
    organizaciones.push(...pagina.results.map((org) => ({ id: org.id, nombre: org.nombre, nivelRol: org.nivel_rol, tipo: org.tipo })))
    if (!pagina.next) return organizaciones
  }
}

export type RolMiembroEditable = 'LECTOR_NV1' | 'OPERATIVO_NV2' | 'AVANZADO_NV3'
type RolMiembro = 'PROPIETARIO' | RolMiembroEditable

interface MiembroApi {
  usuario_id: string
  nombre_completo: string
  correo_electronico: string
  rol: RolMiembro
  fecha_ingreso: string
}

export interface MiembroOrganizacion {
  usuarioId: string
  nombreCompleto: string
  correoElectronico: string
  rol: RolMiembro
  fechaIngreso: string
}

function rutaMiembros(organizacionId: string) {
  return `/organizaciones/${encodeURIComponent(organizacionId)}/miembros/`
}

function rutaMiembro(organizacionId: string, usuarioId: string) {
  return `${rutaMiembros(organizacionId)}${encodeURIComponent(usuarioId)}/`
}

export async function listarMiembros(
  organizacionId: string,
  pagina: number,
  signal: AbortSignal,
): Promise<Pagina<MiembroOrganizacion>> {
  const respuesta = await clienteApi.get<PaginaApi<MiembroApi>>(rutaMiembros(organizacionId), {
    params: { page: pagina, page_size: 25 },
    signal,
  })
  return mapearPagina(respuesta.data, (miembro) => ({
    usuarioId: miembro.usuario_id,
    nombreCompleto: miembro.nombre_completo,
    correoElectronico: miembro.correo_electronico,
    rol: miembro.rol,
    fechaIngreso: miembro.fecha_ingreso,
  }))
}

export async function cambiarRolMiembro(
  organizacionId: string,
  usuarioId: string,
  rol: RolMiembroEditable,
): Promise<string> {
  const respuesta = await clienteApi.patch<RespuestaMensajeApi>(rutaMiembro(organizacionId, usuarioId), { rol })
  return respuesta.data.mensaje
}

export async function retirarMiembro(organizacionId: string, usuarioId: string): Promise<string> {
  const respuesta = await clienteApi.delete<RespuestaMensajeApi>(rutaMiembro(organizacionId, usuarioId))
  return respuesta.data.mensaje
}
