import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import type { MiembroOrganizacion, RolMiembro } from '../../types/administracion'
import {
  ROLES_ASIGNABLES,
  esCorreoValido,
  existeMiembroConCorreo,
  obtenerDescripcionRol,
  obtenerEtiquetaRol,
} from '../../utils/administracion'
import { COLOR_ICONO_FONDO, COLOR_MARCA } from '../../theme/colores'
import VentanaModal from './VentanaModal'

interface ModalInvitarMiembroProps {
  miembros: MiembroOrganizacion[]
  onCerrar: () => void
  onInvitar: (correo: string, rol: RolMiembro) => void
}

const ESTILO_CAMPO: React.CSSProperties = {
  backgroundColor: COLOR_ICONO_FONDO,
  border: 'none',
  borderRadius: '10px',
  padding: '10px 14px',
}

function ModalInvitarMiembro({ miembros, onCerrar, onInvitar }: ModalInvitarMiembroProps) {
  const [correo, setCorreo] = useState('')
  const [rol, setRol] = useState<RolMiembro>('operativo')
  const [error, setError] = useState<string | null>(null)

  function confirmar() {
    if (!esCorreoValido(correo)) {
      setError('Escribe un correo electrónico válido.')
      return
    }
    if (existeMiembroConCorreo(miembros, correo)) {
      setError('Ese correo ya forma parte de la organización.')
      return
    }
    onInvitar(correo.trim().toLowerCase(), rol)
  }

  return (
    <VentanaModal titulo="Invitar usuario" onCerrar={onCerrar}>
      <label htmlFor="correoInvitado" className="form-label small fw-semibold">
        Correo electrónico
      </label>
      <input
        id="correoInvitado"
        type="email"
        className="form-control mb-3"
        style={ESTILO_CAMPO}
        placeholder="nombre@empresa.com"
        value={correo}
        onChange={(evento) => {
          setCorreo(evento.target.value)
          setError(null)
        }}
        onKeyDown={(evento) => {
          if (evento.key === 'Enter') confirmar()
        }}
        autoFocus
      />

      <label htmlFor="rolInvitado" className="form-label small fw-semibold">
        Rol
      </label>
      <select
        id="rolInvitado"
        className="form-select mb-1"
        style={ESTILO_CAMPO}
        value={rol}
        onChange={(evento) => setRol(evento.target.value as RolMiembro)}
      >
        {ROLES_ASIGNABLES.map((opcion) => (
          <option key={opcion} value={opcion}>
            {obtenerEtiquetaRol(opcion)}
          </option>
        ))}
      </select>
      <p className="small mb-3" style={{ color: '#64748B' }}>
        {obtenerDescripcionRol(rol)}
      </p>

      {error && (
        <p role="alert" className="small text-danger">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={confirmar}
        disabled={!correo.trim()}
        className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold"
        style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
      >
        <UserPlus size={18} /> Enviar invitación
      </button>
    </VentanaModal>
  )
}

export default ModalInvitarMiembro