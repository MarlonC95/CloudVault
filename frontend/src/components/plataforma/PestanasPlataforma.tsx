import type { PestanaPlataforma } from '../../types/plataforma'
import { obtenerIdPanel, obtenerIdPestana } from '../../utils/plataforma'
import { COLOR_MARCA } from '../../theme/colores'

const PESTANAS: { id: PestanaPlataforma; etiqueta: string }[] = [
  { id: 'resumen', etiqueta: 'Resumen' },
  { id: 'usuarios', etiqueta: 'Usuarios' },
  { id: 'organizaciones', etiqueta: 'Organizaciones' },
  { id: 'auditoria', etiqueta: 'Auditoría' },
]

interface PestanasPlataformaProps {
  activa: PestanaPlataforma
  onCambiar: (pestana: PestanaPlataforma) => void
}

function PestanasPlataforma({ activa, onCambiar }: PestanasPlataformaProps) {
  return (
    <div
      role="tablist"
      aria-label="Secciones del panel de plataforma"
      className="d-flex gap-1 mb-4"
      style={{ borderBottom: '1px solid #E2E8F0', overflowX: 'auto' }}
    >
      {PESTANAS.map((pestana) => {
        const estaActiva = pestana.id === activa
        return (
          <button
            key={pestana.id}
            id={obtenerIdPestana(pestana.id)}
            type="button"
            role="tab"
            aria-selected={estaActiva}
            aria-controls={obtenerIdPanel(pestana.id)}
            onClick={() => onCambiar(pestana.id)}
            className="btn"
            style={{
              borderRadius: 0,
              padding: '10px 18px',
              fontSize: 13,
              fontWeight: 600,
              whiteSpace: 'nowrap',
              color: estaActiva ? COLOR_MARCA : '#64748B',
              borderBottom: `2px solid ${estaActiva ? COLOR_MARCA : 'transparent'}`,
              marginBottom: -1,
            }}
          >
            {pestana.etiqueta}
          </button>
        )
      })}
    </div>
  )
}

export default PestanasPlataforma