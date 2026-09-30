import { Search, ChevronDown } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO } from '../../theme/colores'

interface BuscadorArchivosProps {
  valorBusqueda: string
  onCambiarBusqueda: (valor: string) => void
}

function BotonFiltro({ etiqueta }: { etiqueta: string }) {
  return (
    <button
      type="button"
      className="btn d-flex align-items-center gap-1 fw-medium bg-white"
      style={{ border: '1px solid #E2E8F0', borderRadius: '50px', color: '#334155' }}
    >
      {etiqueta}
      <ChevronDown size={16} />
    </button>
  )
}

function BuscadorArchivos({ valorBusqueda, onCambiarBusqueda }: BuscadorArchivosProps) {
  return (
    <div className="d-flex flex-wrap gap-2 mb-4">
      <div className="input-group flex-grow-1" style={{ minWidth: '220px' }}>
        <span
          className="input-group-text border-0"
          style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
        >
          <Search size={18} color={COLOR_MARCA} />
        </span>
        <input
          type="text"
          className="form-control border-0"
          style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
          placeholder="Buscar archivos o carpetas..."
          value={valorBusqueda}
          onChange={(evento) => onCambiarBusqueda(evento.target.value)}
        />
      </div>
      <BotonFiltro etiqueta="Tipo" />
      <BotonFiltro etiqueta="Fecha" />
      <BotonFiltro etiqueta="Tamaño" />
    </div>
  )
}

export default BuscadorArchivos