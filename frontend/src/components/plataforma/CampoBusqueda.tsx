import { Search } from 'lucide-react'
import { LIMITE_BUSQUEDA } from '../../utils/plataforma'

interface CampoBusquedaProps {
  valor: string
  onCambiar: (valor: string) => void
  placeholder: string
  etiqueta: string
}

function CampoBusqueda({ valor, onCambiar, placeholder, etiqueta }: CampoBusquedaProps) {
  return (
    <div className="position-relative" style={{ width: '100%', maxWidth: 280 }}>
      <Search
        size={14}
        color="#94A3B8"
        style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
      />
      <input
        type="search"
        aria-label={etiqueta}
        placeholder={placeholder}
        value={valor}
        maxLength={LIMITE_BUSQUEDA}
        onChange={(evento) => onCambiar(evento.target.value)}
        className="form-control"
        style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 13, padding: '8px 12px 8px 32px' }}
      />
    </div>
  )
}

export default CampoBusqueda