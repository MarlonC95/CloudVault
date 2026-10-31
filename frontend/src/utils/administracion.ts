import type {
  EventoAuditoria,
  MiembroOrganizacion,
  RolMiembro,
  SeveridadEvento,
} from '../types/administracion'
import { convertirFilasACsv } from './csv'

/** El propietario no se asigna desde la pantalla: el contrato solo permite roles de nivel 1 a 3. */
export const ROLES_ASIGNABLES: RolMiembro[] = ['avanzado', 'operativo', 'lector']

const ETIQUETAS_ROL: Record<RolMiembro, string> = {
  propietario: 'Propietario',
  avanzado: 'Avanzado',
  operativo: 'Operativo',
  lector: 'Lector',
}

const DESCRIPCIONES_ROL: Record<RolMiembro, string> = {
  propietario: 'Control total de la organización, sus miembros y su plan.',
  avanzado: 'Nivel 3: además puede enviar a la papelera y restaurar.',
  operativo: 'Nivel 2: puede subir, descargar, crear carpetas, renombrar, mover y compartir.',
  lector: 'Nivel 1: solo puede buscar y previsualizar archivos.',
}

const COLORES_ROL: Record<RolMiembro, { fondo: string; texto: string }> = {
  propietario: { fondo: 'rgba(37,99,235,0.08)', texto: '#2563EB' },
  avanzado: { fondo: 'rgba(217,119,6,0.08)', texto: '#D97706' },
  operativo: { fondo: 'rgba(22,163,74,0.08)', texto: '#16A34A' },
  lector: { fondo: 'rgba(100,116,139,0.08)', texto: '#475569' },
}

const COLORES_SEVERIDAD: Record<SeveridadEvento, { fondo: string; texto: string; etiqueta: string }> = {
  info: { fondo: 'rgba(37,99,235,0.08)', texto: '#2563EB', etiqueta: 'Info' },
  advertencia: { fondo: 'rgba(217,119,6,0.08)', texto: '#D97706', etiqueta: 'Advertencia' },
  critica: { fondo: 'rgba(220,38,38,0.08)', texto: '#DC2626', etiqueta: 'Crítica' },
}

export function obtenerEtiquetaRol(rol: RolMiembro): string {
  return ETIQUETAS_ROL[rol]
}

export function obtenerDescripcionRol(rol: RolMiembro): string {
  return DESCRIPCIONES_ROL[rol]
}

export function obtenerColoresRol(rol: RolMiembro) {
  return COLORES_ROL[rol]
}

export function obtenerColoresSeveridad(severidad: SeveridadEvento) {
  return COLORES_SEVERIDAD[severidad]
}

/** "Carlos López" -> "CL". Con una sola palabra devuelve solo su inicial. */
export function obtenerIniciales(nombreCompleto: string): string {
  return nombreCompleto
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((palabra) => palabra.charAt(0).toUpperCase())
    .join('')
}

export function contarMiembrosActivos(miembros: MiembroOrganizacion[]): number {
  return miembros.filter((miembro) => miembro.estado === 'activo').length
}

export function contarEventosCriticos(eventos: EventoAuditoria[]): number {
  return eventos.filter((evento) => evento.severidad === 'critica').length
}

export function existeMiembroConCorreo(miembros: MiembroOrganizacion[], correo: string): boolean {
  const correoNormalizado = correo.trim().toLowerCase()
  return miembros.some((miembro) => miembro.correoElectronico.toLowerCase() === correoNormalizado)
}

/** Validación sencilla para el formulario; el backend hará la validación definitiva. */
export function esCorreoValido(correo: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo.trim())
}

/** Convierte los eventos de auditoría en un CSV que Excel abre bien (con acentos). */
export function convertirEventosACsv(eventos: EventoAuditoria[]): string {
  return convertirFilasACsv(
    ['Fecha (UTC)', 'Evento', 'Severidad'],
    eventos.map((evento) => [evento.fecha, evento.descripcion, obtenerColoresSeveridad(evento.severidad).etiqueta]),
  )
}