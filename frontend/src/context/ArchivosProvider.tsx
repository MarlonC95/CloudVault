import { useState } from 'react'
import type { ReactNode } from 'react'
import { ARCHIVOS_EJEMPLO, CARPETAS_EJEMPLO } from '../data/datosEjemplo'
import { calcularDiasRestantes } from '../utils/papelera'
import type { Archivo, Carpeta } from '../types/archivo'
import { ArchivosContexto } from './archivosContexto'
import type { ArchivosContextoValor } from './archivosContexto'

const COLORES_CARPETA_NUEVA = [
  { color: '#DB2777', colorFondo: '#FDF2F8' },
  { color: '#CA8A04', colorFondo: '#FEFCE8' },
  { color: '#059669', colorFondo: '#ECFDF5' },
]

function archivoSigueVigente(archivo: Archivo): boolean {
  // TODO(backend): el borrado automático a los 30 días lo hará el servidor, no el frontend
  return !archivo.enPapelera || calcularDiasRestantes(archivo.eliminadoEn) > 0
}

interface ArchivosProviderProps {
  children: ReactNode
}

/**
 * Guarda las carpetas y los archivos del usuario en un solo lugar para que
 * "Mi Unidad" y "Papelera" vean siempre los mismos datos.
 */
function ArchivosProvider({ children }: ArchivosProviderProps) {
  const [carpetas, setCarpetas] = useState<Carpeta[]>(CARPETAS_EJEMPLO)
  const [archivos, setArchivos] = useState<Archivo[]>(() => ARCHIVOS_EJEMPLO.filter(archivoSigueVigente))

  function agregarArchivos(nuevosArchivos: Archivo[]) {
    // TODO(backend): reemplazar por POST /api/archivos/
    setArchivos((anteriores) => [...nuevosArchivos, ...anteriores])
  }

  function crearCarpeta(nombre: string) {
    // TODO(backend): reemplazar por POST /api/carpetas/
    const paleta = COLORES_CARPETA_NUEVA[carpetas.length % COLORES_CARPETA_NUEVA.length]
    const nuevaCarpeta: Carpeta = {
      id: `carpeta-${Date.now()}`,
      nombre,
      color: paleta.color,
      colorFondo: paleta.colorFondo,
    }
    setCarpetas((anteriores) => [...anteriores, nuevaCarpeta])
  }

  function moverArchivo(archivoId: string, carpetaId: string | null) {
    // TODO(backend): reemplazar por PATCH /api/archivos/{id}/
    setArchivos((anteriores) =>
      anteriores.map((archivo) => (archivo.id === archivoId ? { ...archivo, carpetaId } : archivo))
    )
  }

  function enviarAPapelera(archivoId: string) {
    // TODO(backend): reemplazar por DELETE /api/archivos/{id}/ (borrado lógico)
    const ahora = new Date().toISOString()
    setArchivos((anteriores) =>
      anteriores.map((archivo) =>
        archivo.id === archivoId ? { ...archivo, enPapelera: true, eliminadoEn: ahora } : archivo
      )
    )
  }

  function restaurarArchivos(archivoIds: string[]) {
    // TODO(backend): reemplazar por POST /api/papelera/restaurar/
    setArchivos((anteriores) =>
      anteriores.map((archivo) =>
        archivoIds.includes(archivo.id) ? { ...archivo, enPapelera: false, eliminadoEn: undefined } : archivo
      )
    )
  }

  function eliminarDefinitivamente(archivoIds: string[]) {
    // TODO(backend): reemplazar por DELETE /api/papelera/{id}/
    setArchivos((anteriores) => anteriores.filter((archivo) => !archivoIds.includes(archivo.id)))
  }

  const valor: ArchivosContextoValor = {
    carpetas,
    archivos,
    agregarArchivos,
    crearCarpeta,
    moverArchivo,
    enviarAPapelera,
    restaurarArchivos,
    eliminarDefinitivamente,
  }

  return <ArchivosContexto.Provider value={valor}>{children}</ArchivosContexto.Provider>
}

export default ArchivosProvider