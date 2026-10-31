import { useCallback, useEffect, useState } from 'react'
import { useOrganizacion } from './organizacionesContexto'
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

async function obtenerCarpetasPapelera(organizacionId: string): Promise<{ carpetas: CarpetaEnPapelera[]; puedeVaciar: boolean }> {
  const carpetas: CarpetaEnPapelera[] = []
  for (let pagina = 1; ; pagina += 1) {
    const respuesta = await listarCarpetasPapelera(pagina, organizacionId)
    carpetas.push(...respuesta.resultados)
    if (!respuesta.urlSiguiente) return { carpetas, puedeVaciar: respuesta.puedeVaciar }
  }
}

function ArchivosProvider({ children }: ArchivosProviderProps) {
  const { organizacion, comprobarSeleccion, ejecutar } = useOrganizacion()
  const organizacionId = organizacion.id
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
      if (!await comprobarSeleccion()) return
      const [unidad, papeleraResultado] = await Promise.allSettled([
        Promise.all([obtenerTodasLasPaginas((pagina) => listarCarpetas(pagina, organizacionId)),
          obtenerTodasLasPaginas((pagina) => listarArchivos({ pagina, organizacionId }))]),
        Promise.all([
          obtenerTodasLasPaginas((pagina) => listarPapelera(pagina, true, organizacionId)),
          obtenerCarpetasPapelera(organizacionId),
          obtenerTodasLasPaginas((pagina) => listarPapelera(pagina, false, organizacionId)),
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
      setCarpetas([])
      setArchivos([])
      setError(convertirEnErrorApi(causa).message)
      throw causa
    } finally {
      setCargando(false)
    }
  }, [organizacionId, comprobarSeleccion])

  useEffect(() => { void Promise.resolve().then(refrescar).catch(() => undefined) }, [refrescar])

  function mutar<T>(accion: () => Promise<T>): Promise<T> {
    return ejecutar(() => mutarEnAmbito(accion))
  }

  async function mutarEnAmbito<T>(accion: () => Promise<T>): Promise<T> {
    setError(null)
    let resultado: T
    try {
      resultado = await accion()
    } catch (causa) {
      try { await refrescar() } catch { /* Se conserva el error original de la operación. */ }
      setCarpetas([])
      setArchivos([])
      setError(convertirEnErrorApi(causa).message)
      throw causa
    }
    await refrescar()
    return resultado
  }

  const valor: ArchivosContextoValor = {
    carpetas, archivos, papelera, papeleraCompleta, carpetasEnPapelera, puedeVaciarPapelera, cargando, error, errorPapelera, refrescar,
    crearCarpeta: (nombre) => mutar(async () => { await crearCarpetaApi(nombre, organizacionId) }),
    renombrarCarpeta: (id, nombre) => mutar(() => actualizarCarpeta(id, { nombre }, organizacionId)),
    renombrarArchivo: (id, nombre) => mutar(() => renombrarArchivoApi(id, nombre, organizacionId)),
    moverArchivo: (id, carpetaId) => mutar(() => moverArchivoApi(id, carpetaId, organizacionId)),
    enviarAPapelera: (id) => mutar(async () => { await enviarArchivoAPapelera(id, organizacionId) }),
    restaurarArchivos: (ids) => mutar(async () => { for (const id of ids) await restaurarArchivoDePapelera(id, organizacionId) }),
    eliminarDefinitivamente: (ids) => mutar(async () => { for (const id of ids) await eliminarDefinitivamenteDePapelera(id, organizacionId) }),
    restaurarCarpetaPapelera: (id) => mutar(async () => { await restaurarCarpetaDePapelera(id, organizacionId) }),
    eliminarCarpetaPapelera: (id) => mutar(() => eliminarCarpetaDePapelera(id, organizacionId)),
    vaciarPapelera: () => mutar(() => vaciarPapeleraApi(organizacionId)),
    reanudarVaciadoPapelera: (id) => mutar(() => reanudarVaciadoPapeleraApi(id, organizacionId)),
    consultarVaciadoPapelera: (id) => consultarVaciadoPapeleraApi(id, organizacionId),
  }

  return <ArchivosContexto.Provider value={valor}>{children}</ArchivosContexto.Provider>
}

export default ArchivosProvider
