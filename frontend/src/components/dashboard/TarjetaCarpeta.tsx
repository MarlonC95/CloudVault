import { Folder, ChevronRight } from 'lucide-react'
import type { Carpeta } from '../../types/archivo'

interface TarjetaCarpetaProps {
  carpeta: Carpeta
}

function TarjetaCarpeta({ carpeta }: TarjetaCarpetaProps) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        cursor: 'pointer',
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 10,
          background: carpeta.colorFondo,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Folder size={20} strokeWidth={1.7} color={carpeta.color} />
      </div>
      <div style={{ minWidth: 0 }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', margin: 0 }}>{carpeta.nombre}</p>
        <p style={{ fontSize: 12, color: '#94A3B8', margin: '2px 0 0' }}>{carpeta.cantidadArchivos} archivos</p>
      </div>
      <ChevronRight size={15} color="#CBD5E1" strokeWidth={2} style={{ marginLeft: 'auto', flexShrink: 0 }} />
    </div>
  )
}

export default TarjetaCarpeta