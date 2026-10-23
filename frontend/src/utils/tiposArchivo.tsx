import { FileText, FileArchive, Image, FileCode, FileSpreadsheet, Video, File } from 'lucide-react'
import type { TipoArchivo } from '../types/archivo'

interface ConfiguracionTipoArchivo {
  etiqueta: string
  colorTexto: string
  colorFondo: string
  Icono: typeof FileText
}

const CONFIGURACION_POR_TIPO: Record<TipoArchivo, ConfiguracionTipoArchivo> = {
  pdf: { etiqueta: 'PDF', colorTexto: '#DC2626', colorFondo: '#FEE2E2', Icono: FileText },
  zip: { etiqueta: 'ZIP', colorTexto: '#B45309', colorFondo: '#FEF3C7', Icono: FileArchive },
  png: { etiqueta: 'PNG', colorTexto: '#059669', colorFondo: '#D1FAE5', Icono: Image },
  js: { etiqueta: 'JS', colorTexto: '#2563EB', colorFondo: '#DBEAFE', Icono: FileCode },
  xlsx: { etiqueta: 'XLS', colorTexto: '#059669', colorFondo: '#D1FAE5', Icono: FileSpreadsheet },
  mp4: { etiqueta: 'MP4', colorTexto: '#7C3AED', colorFondo: '#EDE9FE', Icono: Video },
  docx: { etiqueta: 'DOC', colorTexto: '#2563EB', colorFondo: '#DBEAFE', Icono: FileText },
  otro: { etiqueta: 'ARCHIVO', colorTexto: '#64748B', colorFondo: '#F1F5F9', Icono: File },
}

export function obtenerConfiguracionTipoArchivo(tipo: TipoArchivo): ConfiguracionTipoArchivo {
  return CONFIGURACION_POR_TIPO[tipo]
}