import { clienteApi } from './clienteApi'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi, RespuestaMensajeApi } from '../types/api'
import { obtenerTipoArchivoPorNombre } from '../utils/formatoArchivo'
import type { ArchivoEnPapelera } from '../types/papelera'
import type { CarpetaEnPapelera } from '../types/papelera'

interface ArchivoEnPapeleraApi {
  id: string
  nombre: string
  tipo: string
  tamano_legible: string
  eliminado_en: string | null
  expira_en: string | null
  dias_restantes: number
  carpeta_id: string | null
}

function mapearArchivoEnPapelera(archivo: ArchivoEnPapeleraApi): ArchivoEnPapelera {
  return {
    id: archivo.id,
    nombre: archivo.nombre,
    tipo: obtenerTipoArchivoPorNombre(archivo.nombre),
    tamano: archivo.tamano_legible,
    eliminadoEn: archivo.eliminado_en,
    expiraEn: archivo.expira_en,
    diasRestantes: archivo.dias_restantes,
    carpetaId: archivo.carpeta_id,
  }
}

interface CarpetaEnPapeleraApi {
  id: string
  nombre: string
  tipo_elemento: 'carpeta'
  eliminado_en: string | null
  expira_en: string | null
  dias_restantes: number
  cantidad_elementos: number
  tamano_bytes: number
  puede_purgar: boolean
}

function mapearCarpetaEnPapelera(carpeta: CarpetaEnPapeleraApi): CarpetaEnPapelera {
  return {
    id: carpeta.id,
    nombre: carpeta.nombre,
    tipoElemento: carpeta.tipo_elemento,
    eliminadoEn: carpeta.eliminado_en,
    expiraEn: carpeta.expira_en,
    diasRestantes: carpeta.dias_restantes,
    cantidadElementos: carpeta.cantidad_elementos,
    tamanoBytes: carpeta.tamano_bytes,
    puedePurgar: carpeta.puede_purgar,
  }
}

/** GET /papelera/ (contrato 8): elementos en retención con su cuenta regresiva. */
export async function listarPapelera(pagina: number, soloRaices: boolean, organizacionId: string): Promise<Pagina<ArchivoEnPapelera>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<ArchivoEnPapeleraApi>>>('/papelera/', {
    params: { page: pagina, organizacion_id: organizacionId, ...(soloRaices ? { vista: 'raices' } : {}) },
  })
  return mapearPagina(respuesta.data.data, mapearArchivoEnPapelera)
}

/** GET /papelera/carpetas/: raíces de lotes, separadas del contrato antiguo de archivos. */
export async function listarCarpetasPapelera(pagina: number, organizacionId: string): Promise<Pagina<CarpetaEnPapelera> & { puedeVaciar: boolean }> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<CarpetaEnPapeleraApi> & { puede_vaciar: boolean }>>(
    '/papelera/carpetas/', { params: { page: pagina, organizacion_id: organizacionId } }
  )
  return {
    ...mapearPagina(respuesta.data.data, mapearCarpetaEnPapelera),
    puedeVaciar: respuesta.data.data.puede_vaciar,
  }
}

/** POST /papelera/carpetas/{id}/restaurar/ */
export async function restaurarCarpetaDePapelera(carpetaId: string, organizacionId: string): Promise<string> {
  const respuesta = await clienteApi.post<RespuestaApi<RespuestaMensajeApi>>(
    `/papelera/carpetas/${carpetaId}/restaurar/`, {}, { params: { organizacion_id: organizacionId } }
  )
  return respuesta.data.data.mensaje
}

/** DELETE /papelera/carpetas/{id}/; purga el árbol retenido como selección fija. */
export async function eliminarCarpetaDePapelera(carpetaId: string, organizacionId: string): Promise<void> {
  await clienteApi.delete(`/papelera/carpetas/${carpetaId}/`, { params: { organizacion_id: organizacionId } })
}

export async function vaciarPapelera(organizacionId: string): Promise<string> {
  const respuesta = await clienteApi.post<RespuestaApi<{ operacion_id: string; mensaje: string }>>(
    '/papelera/vaciar/', {}, { params: { organizacion_id: organizacionId } }
  )
  return respuesta.data.data.operacion_id
}

export async function reanudarVaciadoPapelera(operacionId: string, organizacionId: string): Promise<string> {
  const respuesta = await clienteApi.post<RespuestaApi<{ operacion_id: string; mensaje: string }>>(
    `/papelera/vaciados/${operacionId}/`, {}, { params: { organizacion_id: organizacionId } }
  )
  return respuesta.data.data.operacion_id
}

export interface EstadoVaciadoPapelera {
  operacionId: string
  estado: 'completado' | 'pendiente' | 'incompleto'
  total: number
  completados: number
  pendientes: number
  obsoletos: number
}

export async function consultarVaciadoPapelera(operacionId: string, organizacionId: string): Promise<EstadoVaciadoPapelera> {
  const respuesta = await clienteApi.get<RespuestaApi<{
    operacion_id: string
    estado: 'completado' | 'pendiente' | 'incompleto'
    total: number
    completados: number
    pendientes: number
    obsoletos: number
  }>>(`/papelera/vaciados/${operacionId}/`, { params: { organizacion_id: organizacionId } })
  return {
    operacionId: respuesta.data.data.operacion_id,
    estado: respuesta.data.data.estado,
    total: respuesta.data.data.total,
    completados: respuesta.data.data.completados,
    pendientes: respuesta.data.data.pendientes,
    obsoletos: respuesta.data.data.obsoletos,
  }
}

/** POST /papelera/{id}/restaurar/ (contrato 8) */
export async function restaurarArchivoDePapelera(archivoId: string, organizacionId: string): Promise<string> {
  const respuesta = await clienteApi.post<RespuestaApi<RespuestaMensajeApi>>(`/papelera/${archivoId}/restaurar/`, {}, { params: { organizacion_id: organizacionId } })
  return respuesta.data.data.mensaje
}

/** DELETE /papelera/{id}/ (contrato 8): eliminación definitiva, no se puede deshacer. */
export async function eliminarDefinitivamenteDePapelera(archivoId: string, organizacionId: string): Promise<void> {
  await clienteApi.delete(`/papelera/${archivoId}/`, { params: { organizacion_id: organizacionId } })
}
