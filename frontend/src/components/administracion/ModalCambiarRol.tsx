import { useState } from 'react'
import { Check } from 'lucide-react'
import type { MiembroOrganizacion, RolMiembro } from '../../types/administracion'
import { ROLES_ASIGNABLES, obtenerDescripcionRol, obtenerEtiquetaRol } from '../../utils/administracion'
import { COLOR_ICONO_FONDO, COLOR_MARCA } from '../../theme/colores'
import VentanaModal from './VentanaModal'

interface ModalCambiarRolProps {
  miembro: MiembroOrganizacion
  onCerrar: () => void
  onGuardar: (rol: RolMiembro) => void
}

function ModalCambiarRol({ miembro, onCerrar, onGuardar }: ModalCambiarRolProps) {
  const [rolElegido, setRolElegido] = useState<RolMiembro>(miembro.rol)

  return (
    <VentanaModal titulo="Cambiar rol" onCerrar={onCerrar}>
      <p className="small mb-3" style={{ color: '#64748B' }}>
        Elige el nivel de acceso de <strong style={{ color: '#0F172A' }}>{miembro.nombreCompleto}</strong>.
      </p>

      <div className="d-flex flex-column gap-2 mb-3" role="radiogroup" aria-label="Rol">
        {ROLES_ASIGNABLES.map((opcion) => {
          const estaElegido = rolElegido === opcion
          return (
            <button
              key={opcion}
              type="button"
              role="radio"
              aria-checked={estaElegido}
              onClick={() => setRolElegido(opcion)}
              className="btn text-start d-flex align-items-start gap-2"
              style={{
                borderRadius: 12,
                padding: '10px 14px',
                border: `1.5px solid ${estaElegido ? COLOR_MARCA : '#E2E8F0'}`,
                backgroundColor: estaElegido ? COLOR_ICONO_FONDO : '#fff',
              }}
            >
              <span style={{ width: 18, flexShrink: 0, color: COLOR_MARCA, paddingTop: 2 }}>
                {estaElegido && <Check size={16} strokeWidth={3} />}
              </span>
              <span>
                <span className="d-block fw-semibold small" style={{ color: '#0F172A' }}>
                  {obtenerEtiquetaRol(opcion)}
                </span>
                <span className="d-block" style={{ fontSize: 12, color: '#64748B' }}>
                  {obtenerDescripcionRol(opcion)}
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <button
        type="button"
        onClick={() => onGuardar(rolElegido)}
        disabled={rolElegido === miembro.rol}
        className="btn w-100 text-white fw-semibold"
        style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
      >
        Guardar cambios
      </button>
    </VentanaModal>
  )
}

export default ModalCambiarRol