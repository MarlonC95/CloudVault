import { useState } from 'react'
import { X, Link2, Check } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'
import type { Archivo } from '../../types/archivo'

interface ModalCompartirProps {
  archivo: Archivo | null
  onCerrar: () => void
}

function ModalCompartir({ archivo, onCerrar }: ModalCompartirProps) {
  const [copiado, setCopiado] = useState(false)

  if (!archivo) return null

  // La creación de enlaces seguirá local hasta que exista la ruta de enlaces compartidos.
  const enlaceSimulado = `https://cloudvault.app/compartido/${archivo.id}`

  async function copiarEnlace() {
    try {
      await navigator.clipboard.writeText(enlaceSimulado)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch (error) {
      console.error('No se pudo copiar el enlace', error)
    }
  }

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={onCerrar}
    >
      <div
        className="bg-white w-100"
        style={{ maxWidth: '440px', borderRadius: '20px', padding: '24px', margin: '0 16px' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 className="fw-bold mb-0">Compartir archivo</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        <p className="text-secondary small mb-3">
          Cualquier persona con este enlace podrá ver <strong>{archivo.nombre}</strong>.
        </p>

        <div
          className="d-flex align-items-center gap-2 mb-3"
          style={{ border: '1px solid #E2E8F0', borderRadius: '10px', padding: '8px 12px' }}
        >
          <Link2 size={16} className="text-secondary flex-shrink-0" />
          <span className="small text-truncate flex-grow-1">{enlaceSimulado}</span>
        </div>

        <button
          type="button"
          className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold"
          style={{ backgroundColor: copiado ? '#16A34A' : COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
          onClick={copiarEnlace}
        >
          {copiado ? (
            <>
              <Check size={18} /> Enlace copiado
            </>
          ) : (
            <>
              <Link2 size={18} /> Copiar enlace
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default ModalCompartir
