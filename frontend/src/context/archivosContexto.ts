import { createContext, useContext } from 'react'
import type { Archivo, Carpeta } from '../types/archivo'
import type { ArchivoEnPapelera } from '../types/papelera'

export interface ArchivosContextoValor {
  carpetas: Carpeta[]
  archivos: Archivo[]
  papelera: ArchivoEnPapelera[]
  cargando: boolean
  error: string | null
  refrescar: () => Promise<void>
  crearCarpeta: (nombre: string) => Promise<void>
  renombrarCarpeta: (id: string, nombre: string) => Promise<void>
  renombrarArchivo: (id: string, nombre: string) => Promise<void>
  moverArchivo: (archivoId: string, carpetaId: string | null) => Promise<void>
  enviarAPapelera: (archivoId: string) => Promise<void>
  restaurarArchivos: (archivoIds: string[]) => Promise<void>
  eliminarDefinitivamente: (archivoIds: string[]) => Promise<void>
}

export const ArchivosContexto = createContext<ArchivosContextoValor | null>(null)

export function useArchivos(): ArchivosContextoValor {
  const valor = useContext(ArchivosContexto)
  if (!valor) throw new Error('useArchivos debe usarse dentro de <ArchivosProvider>')
  return valor
}
