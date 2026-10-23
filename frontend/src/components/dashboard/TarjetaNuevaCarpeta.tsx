import { Plus } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'

interface TarjetaNuevaCarpetaProps {
  onClick: () => void
}

function TarjetaNuevaCarpeta({ onClick }: TarjetaNuevaCarpetaProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background: '#F8FAFC',
        border: '1.5px dashed #CBD5E1',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        cursor: 'pointer',
        width: '100%',
        textAlign: 'left',
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 10,
          background: '#EFF6FF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Plus size={20} strokeWidth={2} color={COLOR_MARCA} />
      </div>
      <p style={{ fontSize: 14, fontWeight: 600, color: '#64748B', margin: 0 }}>Nueva carpeta</p>
    </button>
  )
}

export default TarjetaNuevaCarpeta