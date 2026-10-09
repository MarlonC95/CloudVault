import axios from 'axios'
import { clienteApi } from './clienteApi'
import { convertirEnErrorApi } from './errorApi'
import { formatearFechaRelativa } from '../utils/fechas'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi, RespuestaMensajeApi } from '../types/api'
import type { Archivo, TipoArchivo } from '../types/archivo'
import type { CargaIniciada, UrlTemporal } from '../types/carga'
import type { RangoFecha, RangoTamano } from '../utils/filtrosArchivos'

interface ArchivoApi {
  id: string
  nombre: string
  tipo: TipoArchivo
  tamano_bytes: number
  tamano_legible: string
  fecha_modificacion: string
  propietario: { id: string; nombre_completo: string }
  cifrado: boolean
  es_nuevo: boolean
  en_papelera: boolean
  carpeta_id: string | null
}

interface CargaIniciadaApi {
  archivo_id: string
  url_subida: string
  metodo: string
  encabezados: Record<string, string>
  expira_en: string
}

interface UrlTemporalApi {
  url_descarga?: string
  url_vista_previa?: string
  nombre?: string
  tipo?: string
  expira_en: string
}

export interface FiltrosArchivos {
  /** Un id para una carpeta, `null` para archivos sin carpeta, o no enviar para ver todos. */
  carpetaId?: string | null
  busqueda?: string
  tipo?: TipoArchivo
  fecha?: RangoFecha
  tamano?: RangoTamano
  pagina?: number
}

function mapearArchivo(archivo: ArchivoApi): Archivo {
  return {
    id: archivo.id,
    nombre: archivo.nombre,
    tipo: archivo.tipo,
    tamano: archivo.tamano_legible,
    fechaModificacion: formatearFechaRelativa(archivo.fecha_modificacion),
    propietario: archivo.propietario.nombre_completo,
    cifrado: archivo.cifrado,
    esNuevo: archivo.es_nuevo,
    enPapelera: archivo.en_papelera,
    carpetaId: archivo.carpeta_id,
  }
}

function construirParametrosListado(filtros: FiltrosArchivos): Record<string, string | number> {
  const parametros: Record<string, string | number> = {}

  if (filtros.carpetaId !== undefined) parametros.carpeta = filtros.carpetaId ?? 'null'
  if (filtros.busqueda?.trim()) parametros.busqueda = filtros.busqueda.trim()
  if (filtros.tipo) parametros.tipo = filtros.tipo
  // 'cualquiera' no se envía. El contrato todavía no tiene un valor para "Más antiguos" (anteriores), así que tampoco se envía.
  if (filtros.fecha && filtros.fecha !== 'cualquiera' && filtros.fecha !== 'anteriores') parametros.fecha = filtros.fecha
  if (filtros.tamano && filtros.tamano !== 'cualquiera') parametros.tamano = filtros.tamano
  if (filtros.pagina) parametros.page = filtros.pagina

  return parametros
}

/** GET /archivos/ (contrato 3.6): lista con búsqueda y filtros. */
export async function listarArchivos(filtros: FiltrosArchivos = {}): Promise<Pagina<Archivo>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<ArchivoApi>>>('/archivos/', {
    params: construirParametrosListado(filtros),
  })
  return mapearPagina(respuesta.data.data, mapearArchivo)
}

/** PATCH /archivos/{id}/ (contrato 3.7): renombra conservando la metadata. */
export async function renombrarArchivo(archivoId: string, nuevoNombre: string): Promise<void> {
  await clienteApi.patch(`/archivos/${archivoId}/`, { nombre: nuevoNombre.trim() })
}

/** DELETE /archivos/{id}/ (contrato 3.8): lo manda a la papelera (retención de 30 días). */
export async function enviarArchivoAPapelera(archivoId: string): Promise<string> {
  const respuesta = await clienteApi.delete<RespuestaApi<RespuestaMensajeApi>>(`/archivos/${archivoId}/`)
  return respuesta.data.data.mensaje
}

/** POST /archivos/{id}/mover/ (contrato 3.9): `null` lo regresa a la raíz. */
export async function moverArchivo(archivoId: string, carpetaId: string | null): Promise<void> {
  await clienteApi.post(`/archivos/${archivoId}/mover/`, { carpeta_id: carpetaId })
}

/** Paso 1 de la carga directa — POST /archivos/iniciar-carga/ (contrato 4.1). */
export async function iniciarCarga(archivo: File, carpetaId: string | null): Promise<CargaIniciada> {
  const respuesta = await clienteApi.post<RespuestaApi<CargaIniciadaApi>>('/archivos/iniciar-carga/', {
    nombre: archivo.name,
    tamano_bytes: archivo.size,
    tipo_mime: archivo.type || 'application/octet-stream',
    carpeta_id: carpetaId,
  })
  const carga = respuesta.data.data
  return {
    archivoId: carga.archivo_id,
    urlSubida: carga.url_subida,
    metodo: carga.metodo,
    encabezados: carga.encabezados,
    expiraEn: carga.expira_en,
  }
}

/** Paso 3 de la carga directa — POST /archivos/{id}/confirmar-carga/ (contrato 4.2). */
export async function confirmarCarga(archivoId: string, etag?: string): Promise<void> {
  await clienteApi.post(`/archivos/${archivoId}/confirmar-carga/`, etag ? { etag } : {})
}

/**
 * Sube un archivo completo en los tres pasos del contrato (sección 4):
 * 1) pedir la URL firmada, 2) enviar el binario directo al storage, 3) confirmar.
 * El binario nunca pasa por Django. `alProgresar` recibe un número de 0 a 100.
 */
export async function subirArchivo(
  archivo: File,
  carpetaId: string | null,
  alProgresar?: (porcentaje: number) => void,
): Promise<string> {
  const carga = await iniciarCarga(archivo, carpetaId)

  let etag: string | undefined
  try {
    // Va con Axios "pelado": la URL firmada ya trae su propia autorización y no debe llevar nuestro token.
    const respuestaStorage = await axios.put(carga.urlSubida, archivo, {
      headers: carga.encabezados,
      onUploadProgress: (evento) => {
        if (alProgresar && evento.total) alProgresar(Math.round((evento.loaded / evento.total) * 100))
      },
    })
    etag = respuestaStorage.headers.etag
  } catch (error) {
    throw convertirEnErrorApi(error)
  }

  await confirmarCarga(carga.archivoId, etag)
  return carga.archivoId
}

async function pedirUrlTemporal(ruta: string, campoUrl: 'url_descarga' | 'url_vista_previa'): Promise<UrlTemporal> {
  const respuesta = await clienteApi.get<RespuestaApi<UrlTemporalApi>>(ruta)
  const datos = respuesta.data.data
  return { url: datos[campoUrl] ?? '', expiraEn: datos.expira_en, nombre: datos.nombre, tipo: datos.tipo }
}

/** GET /archivos/{id}/descarga/ (contrato 5.1) */
export function obtenerUrlDescarga(archivoId: string): Promise<UrlTemporal> {
  return pedirUrlTemporal(`/archivos/${archivoId}/descarga/`, 'url_descarga')
}

/** GET /archivos/{id}/vista-previa/ (contrato 5.2) */
export function obtenerUrlVistaPrevia(archivoId: string): Promise<UrlTemporal> {
  return pedirUrlTemporal(`/archivos/${archivoId}/vista-previa/`, 'url_vista_previa')
}