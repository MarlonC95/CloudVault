import { clienteApi } from './clienteApi'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi, RespuestaMensajeApi } from '../types/api'
import { obtenerTipoArchivoPorNombre } from '../utils/formatoArchivo'
import type { ArchivoEnPapelera } from '../types/papelera'

interface ArchivoEnPapeleraApi {
  id: string
  nombre: string
  tipo: string
  tamano_legible: string
  eliminado_en: string
  expira_en: string
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

/** GET /papelera/ (contrato 8): elementos en retención con su cuenta regresiva. */
export async function listarPapelera(pagina = 1): Promise<Pagina<ArchivoEnPapelera>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<ArchivoEnPapeleraApi>>>('/papelera/', { params: { page: pagina } })
  return mapearPagina(respuesta.data.data, mapearArchivoEnPapelera)
}

/** POST /papelera/{id}/restaurar/ (contrato 8) */
export async function restaurarArchivoDePapelera(archivoId: string): Promise<string> {
  const respuesta = await clienteApi.post<RespuestaApi<RespuestaMensajeApi>>(`/papelera/${archivoId}/restaurar/`)
  return respuesta.data.data.mensaje
}

/** DELETE /papelera/{id}/ (contrato 8): eliminación definitiva, no se puede deshacer. */
export async function eliminarDefinitivamenteDePapelera(archivoId: string): Promise<void> {
  await clienteApi.delete(`/papelera/${archivoId}/`)
}
