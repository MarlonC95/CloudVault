import { clienteApi } from './clienteApi'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi } from '../types/api'
import type { Carpeta } from '../types/archivo'

interface CarpetaApi {
  id: string
  nombre: string
  color?: string
  color_fondo?: string
  cantidad_archivos?: number
  creado_en?: string
}

/** Colores que usamos si el backend no manda los de una carpeta recién creada. */
const COLOR_CARPETA_PREDETERMINADO = '#2563EB'
const COLOR_FONDO_CARPETA_PREDETERMINADO = '#EFF6FF'

export interface CarpetaConConteo extends Carpeta {
  cantidadArchivos: number
}

function mapearCarpeta(carpeta: CarpetaApi): CarpetaConConteo {
  return {
    id: carpeta.id,
    nombre: carpeta.nombre,
    color: carpeta.color ?? COLOR_CARPETA_PREDETERMINADO,
    colorFondo: carpeta.color_fondo ?? COLOR_FONDO_CARPETA_PREDETERMINADO,
    cantidadArchivos: carpeta.cantidad_archivos ?? 0,
  }
}

/** GET /carpetas/ (contrato 3.1). Soporta paginación con `pagina`. */
export async function listarCarpetas(pagina = 1): Promise<Pagina<CarpetaConConteo>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<CarpetaApi>>>('/carpetas/', {
    params: { page: pagina },
  })
  return mapearPagina(respuesta.data.data, mapearCarpeta)
}

/** POST /carpetas/ (contrato 3.2). Si no se mandan colores, el backend usa su paleta. */
export async function crearCarpeta(nombre: string, color?: string, colorFondo?: string): Promise<CarpetaConConteo> {
  const respuesta = await clienteApi.post<RespuestaApi<CarpetaApi>>('/carpetas/', {
    nombre: nombre.trim(),
    color,
    color_fondo: colorFondo,
  })
  return mapearCarpeta(respuesta.data.data)
}

/** PATCH /carpetas/{id}/ (contrato 3.4): renombrar o recolorear. */
export async function actualizarCarpeta(
  carpetaId: string,
  cambios: { nombre?: string; color?: string; colorFondo?: string },
): Promise<void> {
  await clienteApi.patch(`/carpetas/${carpetaId}/`, {
    nombre: cambios.nombre?.trim(),
    color: cambios.color,
    color_fondo: cambios.colorFondo,
  })
}

/** DELETE /carpetas/{id}/ (contrato 3.5). Sus archivos pasan a "Sin carpeta". */
export async function eliminarCarpeta(carpetaId: string): Promise<void> {
  await clienteApi.delete(`/carpetas/${carpetaId}/`)
}