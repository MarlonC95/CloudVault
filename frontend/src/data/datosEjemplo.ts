import type { Archivo, Carpeta, CargaEnProgreso } from '../types/archivo'

export const CARPETAS_EJEMPLO: Carpeta[] = [
  { id: 'documentos', nombre: 'Documentos', color: '#2563EB', colorFondo: '#EFF6FF' },
  { id: 'proyectos', nombre: 'Proyectos', color: '#7C3AED', colorFondo: '#F5F3FF' },
  { id: 'imagenes', nombre: 'Imágenes', color: '#0D9488', colorFondo: '#F0FDFA' },
]

export const ARCHIVOS_EJEMPLO: Archivo[] = [
  { id: '1', nombre: 'Arquitectura_PaaS_v1.pdf', tipo: 'pdf', fechaModificacion: 'Hace 2 horas', tamano: '4.2 MB', propietario: 'Mily Santay', cifrado: true, esNuevo: true, carpetaId: 'documentos' },
  { id: '2', nombre: 'Respaldo_BaseDatos.zip', tipo: 'zip', fechaModificacion: 'Ayer 18:30', tamano: '128 MB', propietario: 'Mily Santay', cifrado: true, carpetaId: null },
  { id: '3', nombre: 'Diagrama_Infraestructura.png', tipo: 'png', fechaModificacion: '28 Ago 2026', tamano: '2.1 MB', propietario: 'Mily Santay', cifrado: false, carpetaId: 'imagenes' },
  { id: '4', nombre: 'Deploy_Pipeline.js', tipo: 'js', fechaModificacion: '25 Ago 2026', tamano: '84 KB', propietario: 'Mily Santay', cifrado: false, carpetaId: 'proyectos' },
  { id: '5', nombre: 'Metricas_Q3_2026.xlsx', tipo: 'xlsx', fechaModificacion: '20 Ago 2026', tamano: '840 KB', propietario: 'Mily Santay', cifrado: false, carpetaId: 'documentos' },
  { id: '6', nombre: 'Demo_Deploy_Pipeline.mp4', tipo: 'mp4', fechaModificacion: '15 Ago 2026', tamano: '1.4 GB', propietario: 'Mily Santay', cifrado: false, carpetaId: 'proyectos' },
]

export const CARGAS_EJEMPLO: CargaEnProgreso[] = [
  { id: 'c1', nombreArchivo: 'Especificaciones_PaaS.pdf', tamano: '3.1 MB', progreso: 85, estado: 'subiendo' },
  { id: 'c2', nombreArchivo: 'Respaldo_BaseDatos.zip', tamano: '128 MB', progreso: 0, estado: 'en-cola' },
]