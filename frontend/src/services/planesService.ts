import { clienteApi } from './clienteApi'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi } from '../types/api'
import type { DatosTarjeta, Factura, MiPlan, Plan, ResultadoSuscripcion, Tarjeta, TipoFacturacion, TipoTarjeta } from '../types/planes'

interface PlanApi {
  id: string
  nombre: string
  precio_mensual: number
  precio_anual: number
  almacenamiento_legible: string
  es_popular: boolean
  caracteristicas: string[]
}

interface MiPlanApi {
  plan: { id: string; nombre: string; tipo_facturacion: TipoFacturacion }
  estado: string
  renueva_en: string
  almacenamiento: {
    usado_bytes: number
    cuota_bytes: number | null
    usado_legible: string
    cuota_legible: string
    libre_legible: string
    porcentaje_usado: number
  }
}

interface FacturaApi {
  id: string
  monto: number
  moneda: string
  estado: string
  periodo_inicio: string
  periodo_fin: string
  url_pdf: string
}

function mapearPlan(plan: PlanApi): Plan {
  return {
    id: plan.id,
    nombre: plan.nombre,
    precioMensual: plan.precio_mensual,
    precioAnual: plan.precio_anual,
    almacenamientoLegible: plan.almacenamiento_legible,
    esPopular: plan.es_popular,
    caracteristicas: plan.caracteristicas,
  }
}

/** GET /planes/ (contrato 10.1): catálogo con precios mensuales y anuales. */
export async function listarPlanes(): Promise<Pagina<Plan>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<PlanApi>>>('/planes/')
  return mapearPagina(respuesta.data.data, mapearPlan)
}

/** GET /mi-plan/ (contrato 10.2): el plan activo del usuario. */
export async function obtenerMiPlan(organizacionId: string): Promise<MiPlan> {
  const respuesta = await clienteApi.get<RespuestaApi<MiPlanApi>>('/mi-plan/', { params: { organizacion_id: organizacionId } })
  const miPlan = respuesta.data.data
  return {
    plan: {
      id: miPlan.plan.id,
      nombre: miPlan.plan.nombre,
      tipoFacturacion: miPlan.plan.tipo_facturacion,
    },
    estado: miPlan.estado,
    renuevaEn: miPlan.renueva_en,
    almacenamiento: {
      usadoBytes: miPlan.almacenamiento.usado_bytes,
      cuotaBytes: miPlan.almacenamiento.cuota_bytes,
      usadoLegible: miPlan.almacenamiento.usado_legible,
      cuotaLegible: miPlan.almacenamiento.cuota_legible,
      libreLegible: miPlan.almacenamiento.libre_legible,
      porcentajeUsado: miPlan.almacenamiento.porcentaje_usado,
    },
  }
}

interface ResultadoSuscripcionApi {
  plan: { id: string; nombre: string; tipo_facturacion: TipoFacturacion }
  estado: string
  renueva_en: string
}

/**
 * POST /mi-plan/suscribir/ (contrato 10.3). Los planes de pago exigen `tarjetaId` (pago simulado).
 * Si el uso actual supera el límite del plan nuevo, lanza un ErrorApi con código CUOTA_EXCEDIDA.
 */
export async function suscribirPlan(
  planId: string,
  tipoFacturacion: TipoFacturacion,
  organizacionId?: string,
  tarjetaId?: string,
): Promise<ResultadoSuscripcion> {
  const respuesta = await clienteApi.post<RespuestaApi<ResultadoSuscripcionApi>>('/mi-plan/suscribir/', {
    plan_id: planId,
    tipo_facturacion: tipoFacturacion,
    organizacion_id: organizacionId,
    tarjeta_id: tarjetaId,
  })
  const resultado = respuesta.data.data
  return {
    plan: {
      id: resultado.plan.id,
      nombre: resultado.plan.nombre,
      tipoFacturacion: resultado.plan.tipo_facturacion,
    },
    estado: resultado.estado,
    renuevaEn: resultado.renueva_en,
  }
}

interface TarjetaApi {
  id: string
  titular: string
  marca: string
  tipo: TipoTarjeta
  ultimos4: string
  mes_expiracion: number
  anio_expiracion: number
  predeterminada: boolean
}

function mapearTarjeta(tarjeta: TarjetaApi): Tarjeta {
  return {
    id: tarjeta.id,
    titular: tarjeta.titular,
    marca: tarjeta.marca,
    tipo: tarjeta.tipo,
    ultimos4: tarjeta.ultimos4,
    mesExpiracion: tarjeta.mes_expiracion,
    anioExpiracion: tarjeta.anio_expiracion,
    predeterminada: tarjeta.predeterminada,
  }
}

function datosTarjetaApi(datos: Partial<DatosTarjeta>) {
  return {
    titular: datos.titular,
    numero: datos.numero,
    cvv: datos.cvv,
    mes_expiracion: datos.mesExpiracion,
    anio_expiracion: datos.anioExpiracion,
    tipo: datos.tipo,
  }
}

/** GET /mi-plan/tarjetas/ (contrato 10.5): máximo 2 tarjetas por organización. */
export async function listarTarjetas(organizacionId: string): Promise<Tarjeta[]> {
  const respuesta = await clienteApi.get<RespuestaApi<TarjetaApi[]>>('/mi-plan/tarjetas/', { params: { organizacion_id: organizacionId } })
  return respuesta.data.data.map(mapearTarjeta)
}

/** POST /mi-plan/tarjetas/ (contrato 10.5) */
export async function guardarTarjeta(datos: DatosTarjeta, organizacionId: string): Promise<Tarjeta> {
  const respuesta = await clienteApi.post<RespuestaApi<TarjetaApi>>('/mi-plan/tarjetas/', { ...datosTarjetaApi(datos), organizacion_id: organizacionId })
  return mapearTarjeta(respuesta.data.data)
}

/** PATCH /mi-plan/tarjetas/{id}/ (contrato 10.5): solo se envían los campos indicados. */
export async function actualizarTarjeta(id: string, cambios: Partial<DatosTarjeta> & { predeterminada?: boolean }, organizacionId: string): Promise<Tarjeta> {
  const respuesta = await clienteApi.patch<RespuestaApi<TarjetaApi>>(`/mi-plan/tarjetas/${id}/`, {
    ...datosTarjetaApi(cambios),
    predeterminada: cambios.predeterminada,
    organizacion_id: organizacionId,
  })
  return mapearTarjeta(respuesta.data.data)
}

/** DELETE /mi-plan/tarjetas/{id}/ (contrato 10.5) */
export async function eliminarTarjeta(id: string, organizacionId: string): Promise<void> {
  await clienteApi.delete(`/mi-plan/tarjetas/${id}/`, { params: { organizacion_id: organizacionId } })
}

/** GET /mi-plan/facturas/ (contrato 10.4) */
export async function listarFacturas(organizacionId: string): Promise<Pagina<Factura>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<FacturaApi>>>('/mi-plan/facturas/', { params: { organizacion_id: organizacionId } })
  return mapearPagina(respuesta.data.data, (factura) => ({
    id: factura.id,
    monto: factura.monto,
    moneda: factura.moneda,
    estado: factura.estado,
    periodoInicio: factura.periodo_inicio,
    periodoFin: factura.periodo_fin,
    urlPdf: factura.url_pdf,
  }))
}
