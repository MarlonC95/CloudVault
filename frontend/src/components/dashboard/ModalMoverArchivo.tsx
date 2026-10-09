import { useState } from 'react'
import { Folder, FolderX, X, Check } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../../services/errorApi'
import type { Archivo, Carpeta } from '../../types/archivo'

interface ModalMoverArchivoProps {
  archivo: Archivo | null
  carpetas: Carpeta[]
  onCerrar: () => void
  onMover: (archivo: Archivo, carpetaId: string | null) => Promise<void>
}

function ModalMoverArchivo({ archivo, carpetas, onCerrar, onMover }: ModalMoverArchivoProps) {
  const [error, setError] = useState<string | null>(null)
  const [moviendo, setMoviendo] = useState(false)
  if (!archivo) return null

  async function mover(carpetaId: string | null) {
    if (!archivo || moviendo) return
    setMoviendo(true)
    setError(null)
    try { await onMover(archivo, carpetaId) }
    catch (causa) {
      const errorApi = convertirEnErrorApi(causa)
      setError(obtenerMensajeDeCampo(errorApi, 'carpeta_id') ?? errorApi.message)
    } finally { setMoviendo(false) }
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
          <h5 className="fw-bold mb-0">Mover archivo</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        <p className="text-secondary small mb-3">
          Elige dónde quieres guardar <strong>{archivo.nombre}</strong>.
        </p>
        {error && <p role="alert" className="small text-danger">{error}</p>}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            type="button"
            onClick={() => { void mover(null) }}
            disabled={moviendo}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              background: archivo.carpetaId === null ? '#EFF6FF' : '#F8FAFC',
              border: `1px solid ${archivo.carpetaId === null ? '#BFDBFE' : '#E2E8F0'}`,
              borderRadius: 10,
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <FolderX size={18} color="#64748B" />
            <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: '#374151' }}>Sin carpeta</span>
            {archivo.carpetaId === null && <Check size={16} color={COLOR_MARCA} />}
          </button>

          {carpetas.map((carpeta) => (
            <button
              key={carpeta.id}
              type="button"
              onClick={() => { void mover(carpeta.id) }}
              disabled={moviendo}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                background: archivo.carpetaId === carpeta.id ? carpeta.colorFondo : '#F8FAFC',
                border: `1px solid ${archivo.carpetaId === carpeta.id ? carpeta.color : '#E2E8F0'}`,
                borderRadius: 10,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <Folder size={18} color={carpeta.color} />
              <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: '#374151' }}>{carpeta.nombre}</span>
              {archivo.carpetaId === carpeta.id && <Check size={16} color={carpeta.color} />}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default ModalMoverArchivo
