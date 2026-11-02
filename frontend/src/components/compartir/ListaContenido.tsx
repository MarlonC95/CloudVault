import { useState } from 'react'
import { Folder, FileText, Eye, Download } from 'lucide-react'
import { convertirEnErrorApi } from '../../services/errorApi'
import { formatearTamanoBytes } from '../../utils/formatoArchivo'
import type { UrlTemporal } from '../../types/carga'

export interface ArchivoListado {
  id: string
  nombre: string
  tamanoBytes: number | null
  permiteDescarga: boolean
}

interface ListaContenidoProps {
  carpetas: { id: string; nombre: string }[]
  archivos: ArchivoListado[]
  onAbrirCarpeta: (carpeta: { id: string; nombre: string }) => void
  obtenerUrl: (archivoId: string, accion: 'ver' | 'descargar') => Promise<UrlTemporal>
}

/** Carpetas y archivos de un recurso compartido, con Ver y (si se permite) Descargar. */
function ListaContenido({ carpetas, archivos, onAbrirCarpeta, obtenerUrl }: ListaContenidoProps) {
  const [error, setError] = useState<string | null>(null)

  async function ver(archivo: ArchivoListado) {
    setError(null)
    // La pestaña se abre antes del await: abrirla después lo bloquea el navegador por no venir de un clic.
    const pestana = window.open('about:blank', '_blank')
    try {
      const { url } = await obtenerUrl(archivo.id, 'ver')
      if (pestana) {
        pestana.opener = null
        pestana.location.href = url
      } else {
        window.location.assign(url)
      }
    } catch (causa) {
      pestana?.close()
      setError(convertirEnErrorApi(causa).message)
    }
  }

  async function descargar(archivo: ArchivoListado) {
    setError(null)
    try {
      const { url, nombre } = await obtenerUrl(archivo.id, 'descargar')
      const enlace = document.createElement('a')
      enlace.href = url
      enlace.download = nombre ?? archivo.nombre
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
    }
  }

  if (carpetas.length === 0 && archivos.length === 0) {
    return <p className="text-secondary small my-4 text-center">Esta carpeta está vacía.</p>
  }

  return (
    <>
      {error && <p role="alert" className="small text-danger">{error}</p>}
      <ul className="list-group">
        {carpetas.map((carpeta) => (
          <li key={carpeta.id} className="list-group-item p-0">
            <button
              type="button"
              className="btn w-100 text-start d-flex align-items-center gap-2 py-2"
              onClick={() => onAbrirCarpeta(carpeta)}
            >
              <Folder size={18} className="text-primary flex-shrink-0" />
              <span className="text-truncate">{carpeta.nombre}</span>
            </button>
          </li>
        ))}
        {archivos.map((archivo) => (
          <li key={archivo.id} className="list-group-item d-flex align-items-center gap-2">
            <FileText size={18} className="text-secondary flex-shrink-0" />
            <span className="text-truncate flex-grow-1">{archivo.nombre}</span>
            {archivo.tamanoBytes !== null && (
              <span className="small text-secondary text-nowrap">{formatearTamanoBytes(archivo.tamanoBytes)}</span>
            )}
            <button type="button" className="btn btn-sm p-1" aria-label={`Ver ${archivo.nombre}`} onClick={() => ver(archivo)}>
              <Eye size={16} />
            </button>
            {archivo.permiteDescarga && (
              <button
                type="button"
                className="btn btn-sm p-1"
                aria-label={`Descargar ${archivo.nombre}`}
                onClick={() => descargar(archivo)}
              >
                <Download size={16} />
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

export default ListaContenido
