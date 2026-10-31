import { useState } from 'react'
import type { UsuarioPlataforma } from '../../types/plataforma'
import { LIMITE_MOTIVO, esMotivoValido } from '../../utils/plataforma'
import { COLOR_ICONO_FONDO, COLOR_MARCA } from '../../theme/colores'
import VentanaModal from '../administracion/VentanaModal'

interface ModalEstadoCuentaProps {
  usuario: UsuarioPlataforma
  onCerrar: () => void
  onConfirmar: (motivo: string) => void
}

/** Pide el motivo (obligatorio según el contrato) antes de habilitar o deshabilitar una cuenta. */
function ModalEstadoCuenta({ usuario, onCerrar, onConfirmar }: ModalEstadoCuentaProps) {
  const [motivo, setMotivo] = useState('')
  const vaADeshabilitar = usuario.estaActivo

  const explicacion = vaADeshabilitar
    ? `${usuario.nombreCompleto} no podrá iniciar sesión y se cerrarán todas sus sesiones abiertas. Sus archivos, planes y membresías se conservan.`
    : `${usuario.nombreCompleto} podrá volver a iniciar sesión. Las sesiones anteriores no se restauran.`

  return (
    <VentanaModal titulo={vaADeshabilitar ? 'Deshabilitar cuenta' : 'Habilitar cuenta'} onCerrar={onCerrar}>
      <p className="small mb-3" style={{ color: '#475569' }}>
        {explicacion}
      </p>

      <label htmlFor="motivoEstadoCuenta" className="form-label small fw-semibold">
        Motivo
      </label>
      <textarea
        id="motivoEstadoCuenta"
        className="form-control mb-1"
        rows={3}
        maxLength={LIMITE_MOTIVO}
        value={motivo}
        onChange={(evento) => setMotivo(evento.target.value)}
        placeholder="Explica por qué cambias el estado de la cuenta"
        style={{ backgroundColor: COLOR_ICONO_FONDO, border: 'none', borderRadius: 10, padding: '10px 14px', resize: 'none' }}
        autoFocus
      />
      <p className="small mb-3 d-flex justify-content-between gap-2" style={{ color: '#94A3B8' }}>
        <span>Queda en el registro de auditoría. No escribas contraseñas ni datos secretos.</span>
        <span>
          {motivo.length}/{LIMITE_MOTIVO}
        </span>
      </p>

      <button
        type="button"
        onClick={() => onConfirmar(motivo.trim())}
        disabled={!esMotivoValido(motivo)}
        className="btn w-100 text-white fw-semibold"
        style={{ backgroundColor: vaADeshabilitar ? '#DC2626' : COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
      >
        {vaADeshabilitar ? 'Deshabilitar cuenta' : 'Habilitar cuenta'}
      </button>
    </VentanaModal>
  )
}

export default ModalEstadoCuenta