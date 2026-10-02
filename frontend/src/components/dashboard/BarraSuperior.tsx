import { useNavigate } from 'react-router-dom'
import { User, LogOut } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO, COLOR_NAVY } from '../../theme/colores'

interface BarraSuperiorProps {
  nombreUsuario: string
  onCerrarSesion: () => void
}

function BotonIcono({
  children,
  onClick,
  ariaLabel,
}: {
  children: React.ReactNode
  onClick?: () => void
  ariaLabel: string
}) {
  return (
    <button
      type="button"
      className="btn d-flex align-items-center justify-content-center flex-shrink-0"
      style={{ width: '38px', height: '38px', borderRadius: '10px', border: 'none', backgroundColor: '#FFFFFF' }}
      onClick={onClick}
      aria-label={ariaLabel}
    >
      {children}
    </button>
  )
}

function BarraSuperior({ nombreUsuario, onCerrarSesion }: BarraSuperiorProps) {
  const navegar = useNavigate()

  return (
    <header
      className="d-flex justify-content-between align-items-center px-4 flex-shrink-0"
      style={{ height: '64px', backgroundColor: COLOR_NAVY }}
    >
      <span className="fw-semibold text-truncate" style={{ color: '#FFFFFF' }}>
        Hola, {nombreUsuario}
      </span>

      <div className="d-flex align-items-center gap-2">
        <button
          type="button"
          onClick={() => navegar('/perfil')}
          className="btn d-flex align-items-center gap-2 fw-semibold flex-shrink-0 text-truncate"
          style={{
            backgroundColor: COLOR_ICONO_FONDO,
            color: COLOR_MARCA,
            borderRadius: '50px',
            padding: '4px 14px 4px 4px',
            border: 'none',
            maxWidth: '180px',
          }}
        >
          <span
            className="d-flex align-items-center justify-content-center flex-shrink-0"
            style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#FFFFFF' }}
          >
            <User size={15} color={COLOR_MARCA} />
          </span>
          <span className="text-truncate small">{nombreUsuario}</span>
        </button>

        <BotonIcono ariaLabel="Cerrar sesión" onClick={onCerrarSesion}>
          <LogOut size={16} color={COLOR_MARCA} />
        </BotonIcono>
      </div>
    </header>
  )
}

export default BarraSuperior