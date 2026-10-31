import type {
  CodigoPlan,
  EventoPlataforma,
  OrganizacionPlataforma,
  PestanaPlataforma,
  UsuarioPlataforma,
} from '../types/plataforma'
import { convertirFilasACsv } from './csv'

/** Máximos que fija el contrato (sección 6). */
export const LIMITE_BUSQUEDA = 100
export const LIMITE_MOTIVO = 500

const ETIQUETAS_PLAN: Record<CodigoPlan, string> = {
  BASICO: 'Básico',
  PREMIUM: 'Premium',
  EMPRESARIAL_PLATINUM: 'Empresarial Platinum',
}

const COLORES_PLAN: Record<CodigoPlan, string> = {
  BASICO: '#64748B',
  PREMIUM: '#2563EB',
  EMPRESARIAL_PLATINUM: '#7C3AED',
}

const ETIQUETAS_TIPO_MIME: Record<string, string> = {
  'application/pdf': 'Documentos PDF',
  'image/jpeg': 'Imágenes JPEG',
  'video/mp4': 'Videos MP4',
  otros: 'Otros',
}

export const CODIGOS_PLAN: CodigoPlan[] = ['BASICO', 'PREMIUM', 'EMPRESARIAL_PLATINUM']

export function obtenerEtiquetaPlan(plan: CodigoPlan): string {
  return ETIQUETAS_PLAN[plan]
}

export function obtenerColorPlan(plan: CodigoPlan): string {
  return COLORES_PLAN[plan]
}

export function obtenerEtiquetaTipoMime(tipo: string): string {
  return ETIQUETAS_TIPO_MIME[tipo] ?? tipo
}

/** "4850.00" -> "$4,850.00". */
export function formatearUsd(monto: string): string {
  const valor = Number(monto)
  return `$${valor.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function calcularPorcentaje(parte: number, total: number): number {
  return total === 0 ? 0 : Math.round((parte / total) * 100)
}

/** El contrato pide un motivo de 1 a 500 caracteres después de recortar los espacios. */
export function esMotivoValido(motivo: string): boolean {
  const longitud = motivo.trim().length
  return longitud >= 1 && longitud <= LIMITE_MOTIVO
}

/** Minúsculas y sin acentos, para que "perez" encuentre "Pérez". */
function normalizarTexto(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function contieneTexto(campos: string[], busqueda: string): boolean {
  const textoBuscado = normalizarTexto(busqueda)
  return textoBuscado === '' || campos.some((campo) => normalizarTexto(campo).includes(textoBuscado))
}

export function filtrarUsuarios(usuarios: UsuarioPlataforma[], busqueda: string): UsuarioPlataforma[] {
  return usuarios.filter((usuario) => contieneTexto([usuario.nombreCompleto, usuario.correoElectronico], busqueda))
}

export function filtrarOrganizaciones(organizaciones: OrganizacionPlataforma[], busqueda: string): OrganizacionPlataforma[] {
  return organizaciones.filter((organizacion) => contieneTexto([organizacion.nombre], busqueda))
}

/** "motivo: Cuenta inactiva · usuario_id: u-3". */
export function describirDetalles(detalles: Record<string, string>): string {
  return Object.entries(detalles)
    .map(([clave, valor]) => `${clave}: ${valor}`)
    .join(' · ')
}

export function filtrarEventos(eventos: EventoPlataforma[], busqueda: string, accion: string): EventoPlataforma[] {
  return eventos.filter((evento) => {
    const coincideAccion = accion === '' || evento.accion === accion
    const coincideTexto = contieneTexto(
      [evento.accion, evento.usuarioNombre ?? '', evento.organizacionNombre ?? '', describirDetalles(evento.detalles)],
      busqueda,
    )
    return coincideAccion && coincideTexto
  })
}

export function obtenerAccionesDisponibles(eventos: EventoPlataforma[]): string[] {
  return [...new Set(eventos.map((evento) => evento.accion))].sort()
}

export function contarPlanes(distribucion: Record<CodigoPlan, number>): number {
  return CODIGOS_PLAN.reduce((total, plan) => total + distribucion[plan], 0)
}

export function convertirEventosPlataformaACsv(eventos: EventoPlataforma[]): string {
  return convertirFilasACsv(
    ['Fecha (UTC)', 'Acción', 'Usuario', 'Organización', 'Detalles'],
    eventos.map((evento) => [
      evento.fechaEvento,
      evento.accion,
      evento.usuarioNombre ?? '',
      evento.organizacionNombre ?? '',
      describirDetalles(evento.detalles),
    ]),
  )
}

/** Identificadores que enlazan cada pestaña con su panel (accesibilidad). */
export function obtenerIdPestana(id: PestanaPlataforma): string {
  return `pestana-${id}`
}

export function obtenerIdPanel(id: PestanaPlataforma): string {
  return `panel-${id}`
}