import { clienteApi } from './clienteApi'
import type { PaginaApi, RespuestaApi } from '../types/api'

export interface OrganizacionDisponible { id: string; nombre: string; nivelRol: number }
interface OrganizacionApi { id: string; nombre: string; nivel_rol: number }

export async function listarOrganizacionesDisponibles(): Promise<OrganizacionDisponible[]> {
  const organizaciones: OrganizacionDisponible[] = []
  for (let page = 1; ; page += 1) {
    const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<OrganizacionApi>>>(
      '/organizaciones/disponibles/', { params: { page, page_size: 100 } })
    const pagina = respuesta.data.data
    organizaciones.push(...pagina.results.map((org) => ({ id: org.id, nombre: org.nombre, nivelRol: org.nivel_rol })))
    if (!pagina.next) return organizaciones
  }
}
