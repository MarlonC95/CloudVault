import { useRef, useState } from 'react'
import { UploadCloud, X, File as FileIcon } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO } from '../../theme/colores'

interface ModalSubirArchivoProps {
  visible: boolean
  onCerrar: () => void
  onConfirmarSubida: (archivos: File[]) => void
}

function ModalSubirArchivo({ visible, onCerrar, onConfirmarSubida }: ModalSubirArchivoProps) {
  const [archivosSeleccionados, setArchivosSeleccionados] = useState<File[]>([])
  const [estaArrastrando, setEstaArrastrando] = useState(false)
  const inputArchivoRef = useRef<HTMLInputElement>(null)

  if (!visible) return null

  function agregarArchivos(listaArchivos: FileList | null) {
    if (!listaArchivos) return
    setArchivosSeleccionados((anteriores) => [...anteriores, ...Array.from(listaArchivos)])
  }

  function quitarArchivo(indice: number) {
    setArchivosSeleccionados((anteriores) => anteriores.filter((_, i) => i !== indice))
  }

  function manejarSoltar(evento: React.DragEvent) {
    evento.preventDefault()
    setEstaArrastrando(false)
    agregarArchivos(evento.dataTransfer.files)
  }

  function confirmar() {
    onConfirmarSubida(archivosSeleccionados)
    setArchivosSeleccionados([])
  }

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={onCerrar}
    >
      <div
        className="bg-white w-100"
        style={{ maxWidth: '480px', borderRadius: '20px', padding: '24px', margin: '0 16px' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="fw-bold mb-0">Subir archivo</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        <div
          className="d-flex flex-column align-items-center justify-content-center text-center mb-3"
          style={{
            border: `2px dashed ${estaArrastrando ? COLOR_MARCA : '#CBD5E1'}`,
            backgroundColor: estaArrastrando ? COLOR_ICONO_FONDO : '#F8FAFC',
            borderRadius: '16px',
            padding: '32px 16px',
            cursor: 'pointer',
          }}
          onDragOver={(evento) => {
            evento.preventDefault()
            setEstaArrastrando(true)
          }}
          onDragLeave={() => setEstaArrastrando(false)}
          onDrop={manejarSoltar}
          onClick={() => inputArchivoRef.current?.click()}
        >
          <UploadCloud size={32} color={COLOR_MARCA} className="mb-2" />
          <p className="fw-semibold mb-1">Arrastra tus archivos aquí</p>
          <p className="small text-secondary mb-0">o haz clic para seleccionarlos desde tu computadora</p>
          <input
            ref={inputArchivoRef}
            type="file"
            multiple
            className="d-none"
            onChange={(evento) => agregarArchivos(evento.target.files)}
          />
        </div>

        {archivosSeleccionados.length > 0 && (
          <div className="mb-3" style={{ maxHeight: '160px', overflowY: 'auto' }}>
            {archivosSeleccionados.map((archivo, indice) => (
              <div
                key={`${archivo.name}-${indice}`}
                className="d-flex align-items-center justify-content-between mb-2"
                style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '10px', padding: '8px 12px' }}
              >
                <div className="d-flex align-items-center gap-2 text-truncate">
                  <FileIcon size={16} color={COLOR_MARCA} />
                  <span className="small text-truncate">{archivo.name}</span>
                </div>
                <button type="button" className="btn btn-sm p-0" onClick={() => quitarArchivo(indice)} aria-label="Quitar">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="btn w-100 text-white fw-semibold py-2"
          style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px' }}
          disabled={archivosSeleccionados.length === 0}
          onClick={confirmar}
        >
          Subir {archivosSeleccionados.length > 0 ? `(${archivosSeleccionados.length})` : ''}
        </button>
      </div>
    </div>
  )
}

export default ModalSubirArchivo