import { clienteApi } from './clienteApi'
import { formatearFechaRelativa } from '../utils/fechas'
import type { RespuestaApi } from '../types/api'
import type { TipoArchivo } from '../types/archivo'
import type { ArchivoReciente, EventoActividad, ResumenAlmacenamiento } from '../types/unidad'

interface ResumenApi {
  usado_bytes: number
  cuota_bytes: number
  usado_legible: string
  cuota_legible: string
  libre_legible: string
  porcentaje_usado: number
  cantidad_archivos: number
  cantidad_carpetas: number
  por_categoria: { etiqueta: string; tamano_legible: string; color: string }[]
}

interface ActividadApi {
  id: string
  accion: string
  descripcion: string
  archivo: string
  creado_en: string
}

interface RecienteApi {
  id: string
  nombre: string
  tipo: TipoArchivo
  tamano_legible: string
  fecha_modificacion: string
}

interface ListaApi<T> {
  results: T[]
}

/** GET /unidad/resumen/ (contrato 3.11): barra de almacenamiento del menú lateral. */
export async function obtenerResumenAlmacenamiento(organizacionId: string): Promise<ResumenAlmacenamiento> {
  const respuesta = await clienteApi.get<RespuestaApi<ResumenApi>>('/unidad/resumen/', { params: { organizacion_id: organizacionId } })
  const resumen = respuesta.data.data
  return {
    usadoBytes: resumen.usado_bytes,
    cuotaBytes: resumen.cuota_bytes,
    usadoLegible: resumen.usado_legible,
    cuotaLegible: resumen.cuota_legible,
    libreLegible: resumen.libre_legible,
    porcentajeUsado: resumen.porcentaje_usado,
    cantidadArchivos: resumen.cantidad_archivos,
    cantidadCarpetas: resumen.cantidad_carpetas,
    porCategoria: resumen.por_categoria.map((categoria) => ({
      etiqueta: categoria.etiqueta,
      tamanoLegible: categoria.tamano_legible,
      color: categoria.color,
    })),
  }
}

/** GET /unidad/actividad/ (contrato 7.1): registro de eventos del usuario. */
export async function listarActividad(organizacionId: string): Promise<EventoActividad[]> {
  const respuesta = await clienteApi.get<RespuestaApi<ListaApi<ActividadApi>>>('/unidad/actividad/', { params: { organizacion_id: organizacionId } })
  return respuesta.data.data.results.map((evento) => ({
    id: evento.id,
    accion: evento.accion,
    descripcion: evento.descripcion,
    archivo: evento.archivo,
    creadoEn: evento.creado_en,
  }))
}

/** GET /recientes/ (contrato 7.2): archivos tocados recientemente. */
export async function listarRecientes(organizacionId: string): Promise<ArchivoReciente[]> {
  const respuesta = await clienteApi.get<RespuestaApi<ListaApi<RecienteApi>>>('/recientes/', { params: { organizacion_id: organizacionId } })
  return respuesta.data.data.results.map((archivo) => ({
    id: archivo.id,
    nombre: archivo.nombre,
    tipo: archivo.tipo,
    tamano: archivo.tamano_legible,
    fechaModificacion: formatearFechaRelativa(archivo.fecha_modificacion),
  }))
}