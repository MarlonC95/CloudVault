import { useState } from 'react'
import { Search, ChevronDown } from 'lucide-react'

interface BuscadorArchivosProps {
  valorBusqueda: string
  onCambiarBusqueda: (valor: string) => void
}

function BuscadorArchivos({ valorBusqueda, onCambiarBusqueda }: BuscadorArchivosProps) {
  const [enfocado, setEnfocado] = useState(false)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ position: 'relative', flex: 1 }}>
        <div
          style={{
            position: 'absolute',
            left: 13,
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            display: 'flex',
          }}
        >
          <Search size={15} strokeWidth={1.9} color={enfocado ? '#2563EB' : '#94A3B8'} />
        </div>
        <input
          value={valorBusqueda}
          onChange={(evento) => onCambiarBusqueda(evento.target.value)}
          onFocus={() => setEnfocado(true)}
          onBlur={() => setEnfocado(false)}
          placeholder="Buscar archivos o carpetas..."
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '10px 14px 10px 38px',
            fontSize: 13,
            color: '#0F172A',
            background: '#fff',
            border: `1.5px solid ${enfocado ? '#2563EB' : '#E2E8F0'}`,
            borderRadius: 9,
            outline: 'none',
          }}
        />
      </div>

      {(['Tipo', 'Fecha', 'Tamaño'] as const).map((filtro) => (
        <button
          key={filtro}
          type="button"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '9px 13px',
            background: '#fff',
            border: '1.5px solid #E2E8F0',
            borderRadius: 9,
            fontSize: 13,
            fontWeight: 500,
            color: '#374151',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
        >
          {filtro}
          <ChevronDown size={13} color="#94A3B8" strokeWidth={2} />
        </button>
      ))}
    </div>
  )
}

export default BuscadorArchivos