import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Archivo, Carpeta } from '../types/archivo'
import type { ArchivoEnPapelera } from '../types/papelera'
import { listarArchivos, moverArchivo as moverArchivoApi, enviarArchivoAPapelera, renombrarArchivo as renombrarArchivoApi } from '../services/archivosService'
import { listarCarpetas, crearCarpeta as crearCarpetaApi, actualizarCarpeta } from '../services/carpetasService'
import { listarPapelera, restaurarArchivoDePapelera, eliminarDefinitivamenteDePapelera } from '../services/papeleraService'
import { convertirEnErrorApi } from '../services/errorApi'
import { ArchivosContexto } from './archivosContexto'
import type { ArchivosContextoValor } from './archivosContexto'

interface ArchivosProviderProps { children: ReactNode }

async function obtenerTodasLasPaginas<T>(listar: (pagina: number) => Promise<{ resultados: T[]; urlSiguiente: string | null }>): Promise<T[]> {
  const elementos: T[] = []
  for (let pagina = 1; ; pagina += 1) {
    const respuesta = await listar(pagina)
    elementos.push(...respuesta.resultados)
    if (!respuesta.urlSiguiente) return elementos
  }
}

function ArchivosProvider({ children }: ArchivosProviderProps) {
  const [carpetas, setCarpetas] = useState<Carpeta[]>([])
  const [archivos, setArchivos] = useState<Archivo[]>([])
  const [papelera, setPapelera] = useState<ArchivoEnPapelera[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refrescar = useCallback(async () => {
    setCargando(true)
    setError(null)
    try {
      const [nuevasCarpetas, nuevosArchivos, nuevaPapelera] = await Promise.all([
        obtenerTodasLasPaginas(listarCarpetas),
        obtenerTodasLasPaginas((pagina) => listarArchivos({ pagina })),
        obtenerTodasLasPaginas(listarPapelera),
      ])
      setCarpetas(nuevasCarpetas)
      setArchivos(nuevosArchivos)
      setPapelera(nuevaPapelera)
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
      throw causa
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { void Promise.resolve().then(refrescar).catch(() => undefined) }, [refrescar])

  async function mutar(accion: () => Promise<unknown>): Promise<void> {
    setError(null)
    try {
      await accion()
    } catch (causa) {
      try { await refrescar() } catch { /* Se conserva el error original de la operación. */ }
      setError(convertirEnErrorApi(causa).message)
      throw causa
    }
    await refrescar()
  }

  const valor: ArchivosContextoValor = {
    carpetas, archivos, papelera, cargando, error, refrescar,
    crearCarpeta: (nombre) => mutar(() => crearCarpetaApi(nombre)),
    renombrarCarpeta: (id, nombre) => mutar(() => actualizarCarpeta(id, { nombre })),
    renombrarArchivo: (id, nombre) => mutar(() => renombrarArchivoApi(id, nombre)),
    moverArchivo: (id, carpetaId) => mutar(() => moverArchivoApi(id, carpetaId)),
    enviarAPapelera: (id) => mutar(() => enviarArchivoAPapelera(id)),
    restaurarArchivos: (ids) => mutar(async () => { for (const id of ids) await restaurarArchivoDePapelera(id) }),
    eliminarDefinitivamente: (ids) => mutar(async () => { for (const id of ids) await eliminarDefinitivamenteDePapelera(id) }),
  }

  return <ArchivosContexto.Provider value={valor}>{children}</ArchivosContexto.Provider>
}

export default ArchivosProvider
