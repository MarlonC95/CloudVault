import { clienteApi } from './clienteApi'
import { mapearPagina } from '../types/api'
import type { PaginaApi, Pagina, RespuestaApi } from '../types/api'
import type { Factura, MiPlan, Plan, TipoFacturacion } from '../types/planes'

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
  almacenamiento: { porcentaje_usado: number }
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
export async function obtenerMiPlan(): Promise<MiPlan> {
  const respuesta = await clienteApi.get<RespuestaApi<MiPlanApi>>('/mi-plan/')
  const miPlan = respuesta.data.data
  return {
    plan: {
      id: miPlan.plan.id,
      nombre: miPlan.plan.nombre,
      tipoFacturacion: miPlan.plan.tipo_facturacion,
    },
    estado: miPlan.estado,
    renuevaEn: miPlan.renueva_en,
    porcentajeUsado: miPlan.almacenamiento.porcentaje_usado,
  }
}

/**
 * POST /mi-plan/suscribir/ (contrato 10.3).
 * Si el uso actual supera el límite del plan nuevo, lanza un ErrorApi con código CUOTA_EXCEDIDA.
 */
export async function suscribirPlan(planId: string, tipoFacturacion: TipoFacturacion): Promise<void> {
  await clienteApi.post('/mi-plan/suscribir/', { plan_id: planId, tipo_facturacion: tipoFacturacion })
}

/** GET /mi-plan/facturas/ (contrato 10.4) */
export async function listarFacturas(): Promise<Pagina<Factura>> {
  const respuesta = await clienteApi.get<RespuestaApi<PaginaApi<FacturaApi>>>('/mi-plan/facturas/')
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