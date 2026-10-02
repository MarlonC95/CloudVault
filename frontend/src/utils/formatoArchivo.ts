import type { TipoArchivo } from '../types/archivo'

const EXTENSIONES: Record<string, TipoArchivo> = {
  pdf: 'pdf',
  zip: 'zip',
  rar: 'zip',
  png: 'png',
  jpg: 'png',
  jpeg: 'png',
  gif: 'png',
  js: 'js',
  ts: 'js',
  tsx: 'js',
  jsx: 'js',
  xlsx: 'xlsx',
  xls: 'xlsx',
  csv: 'xlsx',
  mp4: 'mp4',
  mov: 'mp4',
  doc: 'docx',
  docx: 'docx',
}

export function obtenerTipoArchivoPorNombre(nombre: string): TipoArchivo {
  const extension = nombre.split('.').pop()?.toLowerCase() ?? ''
  return EXTENSIONES[extension] ?? 'otro'
}

export function formatearTamanoBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}