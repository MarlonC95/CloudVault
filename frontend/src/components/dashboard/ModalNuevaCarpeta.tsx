import { useState } from 'react'
import { X, FolderPlus } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO } from '../../theme/colores'

interface ModalNuevaCarpetaProps {
  visible: boolean
  onCerrar: () => void
  onCrear: (nombre: string) => void
}

function ModalNuevaCarpeta({ visible, onCerrar, onCrear }: ModalNuevaCarpetaProps) {
  const [nombre, setNombre] = useState('')

  if (!visible) return null

  function confirmar() {
    if (!nombre.trim()) return
    onCrear(nombre.trim())
    setNombre('')
  }

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={onCerrar}
    >
      <div
        className="bg-white w-100"
        style={{ maxWidth: '400px', borderRadius: '20px', padding: '24px', margin: '0 16px' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="fw-bold mb-0">Nueva carpeta</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        <label htmlFor="nombreCarpeta" className="form-label small fw-semibold">
          Nombre de la carpeta
        </label>
        <input
          id="nombreCarpeta"
          type="text"
          className="form-control mb-3"
          style={{ backgroundColor: COLOR_ICONO_FONDO, border: 'none', borderRadius: '10px', padding: '10px 14px' }}
          placeholder="Ej. Contratos 2026"
          value={nombre}
          onChange={(evento) => setNombre(evento.target.value)}
          onKeyDown={(evento) => evento.key === 'Enter' && confirmar()}
          autoFocus
        />

        <button
          type="button"
          onClick={confirmar}
          disabled={!nombre.trim()}
          className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold"
          style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
        >
          <FolderPlus size={18} /> Crear carpeta
        </button>
      </div>
    </div>
  )
}

export default ModalNuevaCarpeta