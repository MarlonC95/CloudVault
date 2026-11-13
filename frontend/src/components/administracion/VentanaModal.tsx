import type { ReactNode } from 'react'
import { X } from 'lucide-react'

interface VentanaModalProps {
  titulo: string
  onCerrar: () => void
  children: ReactNode
}

/** Estructura común de las ventanas emergentes de Administración: fondo oscuro, tarjeta y botón de cerrar. */
function VentanaModal({ titulo, onCerrar, children }: VentanaModalProps) {
  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={onCerrar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className="bg-white w-100"
        style={{ maxWidth: '440px', borderRadius: '20px', padding: '24px', margin: '0 16px' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="fw-bold mb-0">{titulo}</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default VentanaModal