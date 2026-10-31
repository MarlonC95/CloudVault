import { createContext, useContext } from 'react'
import type { Archivo, Carpeta } from '../types/archivo'
import type { ArchivoEnPapelera } from '../types/papelera'
import type { CarpetaEnPapelera } from '../types/papelera'
import type { EstadoVaciadoPapelera } from '../services/papeleraService'

export interface ArchivosContextoValor {
  carpetas: Carpeta[]
  archivos: Archivo[]
  papelera: ArchivoEnPapelera[]
  papeleraCompleta: ArchivoEnPapelera[]
  carpetasEnPapelera: CarpetaEnPapelera[]
  puedeVaciarPapelera: boolean
  cargando: boolean
  errorPapelera: string | null
  error: string | null
  refrescar: () => Promise<void>
  crearCarpeta: (nombre: string) => Promise<void>
  renombrarCarpeta: (id: string, nombre: string) => Promise<void>
  renombrarArchivo: (id: string, nombre: string) => Promise<void>
  moverArchivo: (archivoId: string, carpetaId: string | null) => Promise<void>
  enviarAPapelera: (archivoId: string) => Promise<void>
  restaurarArchivos: (archivoIds: string[]) => Promise<void>
  eliminarDefinitivamente: (archivoIds: string[]) => Promise<void>
  restaurarCarpetaPapelera: (carpetaId: string) => Promise<void>
  eliminarCarpetaPapelera: (carpetaId: string) => Promise<void>
  vaciarPapelera: () => Promise<string>
  reanudarVaciadoPapelera: (operacionId: string) => Promise<string>
  consultarVaciadoPapelera: (operacionId: string) => Promise<EstadoVaciadoPapelera>
}

export const ArchivosContexto = createContext<ArchivosContextoValor | null>(null)

export function useArchivos(): ArchivosContextoValor {
  const valor = useContext(ArchivosContexto)
  if (!valor) throw new Error('useArchivos debe usarse dentro de <ArchivosProvider>')
  return valor
}
