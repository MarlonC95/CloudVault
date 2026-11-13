import { createContext, useContext } from 'react'
import type { OrganizacionDisponible } from '../services/organizacionesService'

export interface OrganizacionesContextoValor {
  organizacion: OrganizacionDisponible
  organizaciones: OrganizacionDisponible[]
  seleccionarOrganizacion: (id: string) => void
  recargarOrganizaciones: () => Promise<void>
  abrirCrearOrganizacion: () => void
  ocupadoOrganizacion: boolean
  comprobarSeleccion: () => Promise<boolean>
  ejecutar: <T>(accion: () => Promise<T>) => Promise<T>
}
export const OrganizacionesContexto = createContext<OrganizacionesContextoValor | null>(null)
export function useOrganizacion() {
  const contexto = useContext(OrganizacionesContexto)
  if (!contexto) throw new Error('Falta la organización seleccionada.')
  return contexto
}
