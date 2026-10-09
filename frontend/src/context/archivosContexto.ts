import { createContext, useContext } from 'react'
import type { Archivo, Carpeta } from '../types/archivo'

export interface ArchivosContextoValor {
  carpetas: Carpeta[]
  /** Todos los archivos, incluidos los que están en la papelera. */
  archivos: Archivo[]
  agregarArchivos: (nuevosArchivos: Archivo[]) => void
  crearCarpeta: (nombre: string) => void
  moverArchivo: (archivoId: string, carpetaId: string | null) => void
  enviarAPapelera: (archivoId: string) => void
  restaurarArchivos: (archivoIds: string[]) => void
  eliminarDefinitivamente: (archivoIds: string[]) => void
}

export const ArchivosContexto = createContext<ArchivosContextoValor | null>(null)

export function useArchivos(): ArchivosContextoValor {
  const valor = useContext(ArchivosContexto)
  if (!valor) {
    throw new Error('useArchivos debe usarse dentro de <ArchivosProvider>')
  }
  return valor
}