import VentanaModal from './VentanaModal'

interface ModalConfirmacionProps {
  titulo: string
  mensaje: string
  etiquetaConfirmar: string
  onConfirmar: () => void
  onCerrar: () => void
}

/** Pregunta de confirmación para acciones que no se pueden deshacer, como quitar a un miembro. */
function ModalConfirmacion({ titulo, mensaje, etiquetaConfirmar, onConfirmar, onCerrar }: ModalConfirmacionProps) {
  return (
    <VentanaModal titulo={titulo} onCerrar={onCerrar}>
      <p className="small mb-4" style={{ color: '#475569' }}>
        {mensaje}
      </p>
      <div className="d-flex gap-2">
        <button
          type="button"
          onClick={onCerrar}
          className="btn flex-fill fw-semibold"
          style={{ border: '1px solid #E2E8F0', borderRadius: '50px', padding: '10px' }}
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={onConfirmar}
          className="btn flex-fill text-white fw-semibold"
          style={{ backgroundColor: '#DC2626', borderRadius: '50px', padding: '10px' }}
        >
          {etiquetaConfirmar}
        </button>
      </div>
    </VentanaModal>
  )
}

export default ModalConfirmacion