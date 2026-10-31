import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Archivo, Carpeta } from '../types/archivo'
import type { ArchivoEnPapelera, CarpetaEnPapelera } from '../types/papelera'
import { listarArchivos, moverArchivo as moverArchivoApi, enviarArchivoAPapelera, renombrarArchivo as renombrarArchivoApi } from '../services/archivosService'
import { listarCarpetas, crearCarpeta as crearCarpetaApi, actualizarCarpeta } from '../services/carpetasService'
import {
  eliminarCarpetaDePapelera,
  eliminarDefinitivamenteDePapelera,
  consultarVaciadoPapelera as consultarVaciadoPapeleraApi,
  listarCarpetasPapelera,
  listarPapelera,
  reanudarVaciadoPapelera as reanudarVaciadoPapeleraApi,
  restaurarArchivoDePapelera,
  restaurarCarpetaDePapelera,
  vaciarPapelera as vaciarPapeleraApi,
} from '../services/papeleraService'
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

async function obtenerCarpetasPapelera(): Promise<{ carpetas: CarpetaEnPapelera[]; puedeVaciar: boolean }> {
  const carpetas: CarpetaEnPapelera[] = []
  for (let pagina = 1; ; pagina += 1) {
    const respuesta = await listarCarpetasPapelera(pagina)
    carpetas.push(...respuesta.resultados)
    if (!respuesta.urlSiguiente) return { carpetas, puedeVaciar: respuesta.puedeVaciar }
  }
}

function ArchivosProvider({ children }: ArchivosProviderProps) {
  const [carpetas, setCarpetas] = useState<Carpeta[]>([])
  const [archivos, setArchivos] = useState<Archivo[]>([])
  const [papelera, setPapelera] = useState<ArchivoEnPapelera[]>([])
  const [papeleraCompleta, setPapeleraCompleta] = useState<ArchivoEnPapelera[]>([])
  const [carpetasEnPapelera, setCarpetasEnPapelera] = useState<CarpetaEnPapelera[]>([])
  const [puedeVaciarPapelera, setPuedeVaciarPapelera] = useState(false)
  const [errorPapelera, setErrorPapelera] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refrescar = useCallback(async () => {
    setCargando(true)
    setError(null)
    try {
      const [unidad, papeleraResultado] = await Promise.allSettled([
        Promise.all([obtenerTodasLasPaginas(listarCarpetas),
          obtenerTodasLasPaginas((pagina) => listarArchivos({ pagina }))]),
        Promise.all([
          obtenerTodasLasPaginas((pagina) => listarPapelera(pagina, true)),
          obtenerCarpetasPapelera(),
          obtenerTodasLasPaginas(listarPapelera),
        ]),
      ])
      setErrorPapelera(null)
      if (papeleraResultado.status === 'fulfilled') {
        setPapelera(papeleraResultado.value[0])
        setCarpetasEnPapelera(papeleraResultado.value[1].carpetas)
        setPuedeVaciarPapelera(papeleraResultado.value[1].puedeVaciar)
        setPapeleraCompleta(papeleraResultado.value[2])
      }
      else {
        setPapelera([])
        setPapeleraCompleta([])
        setCarpetasEnPapelera([])
        setPuedeVaciarPapelera(false)
        setErrorPapelera(convertirEnErrorApi(papeleraResultado.reason).message)
      }
      if (unidad.status === 'rejected') throw unidad.reason
      setCarpetas(unidad.value[0])
      setArchivos(unidad.value[1])
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
      throw causa
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => { void Promise.resolve().then(refrescar).catch(() => undefined) }, [refrescar])

  async function mutar<T>(accion: () => Promise<T>): Promise<T> {
    setError(null)
    let resultado: T
    try {
      resultado = await accion()
    } catch (causa) {
      try { await refrescar() } catch { /* Se conserva el error original de la operación. */ }
      setError(convertirEnErrorApi(causa).message)
      throw causa
    }
    await refrescar()
    return resultado
  }

  const valor: ArchivosContextoValor = {
    carpetas, archivos, papelera, papeleraCompleta, carpetasEnPapelera, puedeVaciarPapelera, cargando, error, errorPapelera, refrescar,
    crearCarpeta: (nombre) => mutar(async () => { await crearCarpetaApi(nombre) }),
    renombrarCarpeta: (id, nombre) => mutar(() => actualizarCarpeta(id, { nombre })),
    renombrarArchivo: (id, nombre) => mutar(() => renombrarArchivoApi(id, nombre)),
    moverArchivo: (id, carpetaId) => mutar(() => moverArchivoApi(id, carpetaId)),
    enviarAPapelera: (id) => mutar(async () => { await enviarArchivoAPapelera(id) }),
    restaurarArchivos: (ids) => mutar(async () => { for (const id of ids) await restaurarArchivoDePapelera(id) }),
    eliminarDefinitivamente: (ids) => mutar(async () => { for (const id of ids) await eliminarDefinitivamenteDePapelera(id) }),
    restaurarCarpetaPapelera: (id) => mutar(async () => { await restaurarCarpetaDePapelera(id) }),
    eliminarCarpetaPapelera: (id) => mutar(() => eliminarCarpetaDePapelera(id)),
    vaciarPapelera: () => mutar(vaciarPapeleraApi),
    reanudarVaciadoPapelera: (id) => mutar(() => reanudarVaciadoPapeleraApi(id)),
    consultarVaciadoPapelera: consultarVaciadoPapeleraApi,
  }

  return <ArchivosContexto.Provider value={valor}>{children}</ArchivosContexto.Provider>
}

export default ArchivosProvider
