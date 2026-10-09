import { useState } from 'react'
import { Upload, ChevronDown, ChevronUp, X } from 'lucide-react'
import { COLOR_MARCA, COLOR_NAVY } from '../../theme/colores'
import type { CargaEnProgreso } from '../../types/archivo'

interface NotificacionCargasProps {
  cargas: CargaEnProgreso[]
}

function NotificacionCargas({ cargas }: NotificacionCargasProps) {
const [estaExpandida, setEstaExpandida] = useState(false)
  if (cargas.length === 0) return null

  return (
    <div
      className="position-fixed text-white shadow-lg"
      style={{
        bottom: '20px',
        right: '20px',
        width: estaExpandida ? '320px' : 'auto',
        backgroundColor: COLOR_NAVY,
        borderRadius: '14px',
        zIndex: 1050,
      }}
    >
      <button
        type="button"
        className="btn d-flex justify-content-between align-items-center w-100 px-3 py-3 text-white border-0"
        onClick={() => setEstaExpandida(!estaExpandida)}
      >
        <span className="d-flex align-items-center gap-2 fw-semibold small">
          <Upload size={16} />
          Subiendo {cargas.length} archivos...
        </span>
        <span className="d-flex align-items-center gap-1 ms-3">
          {estaExpandida ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </span>
      </button>

      {estaExpandida && (
        <div className="px-3 pb-3" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <div className="d-flex justify-content-end pt-2">
            <button
              type="button"
              className="btn btn-sm p-1 text-white"
              onClick={() => setEstaExpandida(false)}
              aria-label="Minimizar"
            >
              <X size={14} />
            </button>
          </div>
          {cargas.map((carga) => (
            <div key={carga.id} className="pt-1">
              <div className="d-flex justify-content-between small mb-1">
                <span className="text-truncate" style={{ maxWidth: '200px' }}>
                  {carga.nombreArchivo}
                </span>
                {carga.estado === 'en-cola' ? (
                  <span
                    className="fw-semibold"
                    style={{ backgroundColor: '#F59E0B', color: '#1E293B', borderRadius: '6px', fontSize: '10px', padding: '2px 6px' }}
                  >
                    En cola
                  </span>
                ) : (
                  <span className="fw-semibold" style={{ color: COLOR_MARCA }}>
                    {carga.progreso}%
                  </span>
                )}
              </div>
              <div style={{ height: '4px', borderRadius: '2px', backgroundColor: 'rgba(255,255,255,0.15)' }}>
                <div
                  style={{ height: '100%', width: `${carga.progreso}%`, borderRadius: '2px', backgroundColor: COLOR_MARCA }}
                />
              </div>
              <div className="small mt-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
                {carga.tamano} {carga.estado === 'en-cola' ? '· Esperando...' : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default NotificacionCargas