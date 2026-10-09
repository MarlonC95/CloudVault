import type { Archivo } from '../types/archivo'
import { parsearTamanoAMb } from './filtrosArchivos'
import { formatearFechaCorta } from './fechas'
import { formatearTamanoBytes } from './formatoArchivo'

export const DIAS_RETENCION_PAPELERA = 30
export const MILISEGUNDOS_POR_DIA = 24 * 60 * 60 * 1000

/** Días que le quedan a un archivo en la papelera antes de borrarse de forma permanente. */
export function calcularDiasRestantes(eliminadoEn?: string): number {
  if (!eliminadoEn) return DIAS_RETENCION_PAPELERA

  const diasTranscurridos = Math.floor((Date.now() - new Date(eliminadoEn).getTime()) / MILISEGUNDOS_POR_DIA)
  return Math.max(0, DIAS_RETENCION_PAPELERA - diasTranscurridos)
}

/** Fecha en la que el archivo pasó a la papelera, por ejemplo "02 Sep 2026". */
export function formatearFechaEliminacion(eliminadoEn?: string): string {
  return eliminadoEn ? formatearFechaCorta(eliminadoEn) : '—'
}

/** Suma el tamaño de varios archivos y lo devuelve legible, por ejemplo "1.5 GB". */
export function calcularTamanoTotalLegible(archivos: Archivo[]): string {
  const totalMb = archivos.reduce((suma, archivo) => suma + parsearTamanoAMb(archivo.tamano), 0)
  if (totalMb === 0) return '0 MB'
  return formatearTamanoBytes(totalMb * 1024 * 1024)
}

interface ColoresDiasRestantes {
  texto: string
  fondo: string
  borde: string
}

/** Verde si queda bastante tiempo, ámbar si queda poco y rojo si está por expirar. */
export function obtenerColoresDiasRestantes(diasRestantes: number): ColoresDiasRestantes {
  if (diasRestantes <= 7) {
    return { texto: '#DC2626', fondo: 'rgba(220,38,38,0.08)', borde: 'rgba(220,38,38,0.15)' }
  }
  if (diasRestantes <= 14) {
    return { texto: '#D97706', fondo: 'rgba(217,119,6,0.08)', borde: 'rgba(217,119,6,0.2)' }
  }
  return { texto: '#16A34A', fondo: 'rgba(22,163,74,0.08)', borde: 'rgba(22,163,74,0.2)' }
}