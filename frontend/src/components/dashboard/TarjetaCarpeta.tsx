import { Folder, ChevronRight } from 'lucide-react'
import type { Carpeta } from '../../types/archivo'

interface TarjetaCarpetaProps {
  carpeta: Carpeta
}

function TarjetaCarpeta({ carpeta }: TarjetaCarpetaProps) {
  return (
    <button
      type="button"
      className="btn d-flex align-items-center justify-content-between text-start w-100 bg-white"
      style={{ border: '1px solid #E2E8F0', borderRadius: '16px', padding: '16px' }}
    >
      <div className="d-flex align-items-center gap-3">
        <div
          className="d-flex align-items-center justify-content-center flex-shrink-0"
          style={{ width: '44px', height: '44px', backgroundColor: carpeta.colorFondo, borderRadius: '12px' }}
        >
          <Folder size={20} color={carpeta.color} />
        </div>
        <div>
          <div className="fw-semibold" style={{ color: '#0F172A' }}>
            {carpeta.nombre}
          </div>
          <div className="small text-secondary">{carpeta.cantidadArchivos} archivos</div>
        </div>
      </div>
      <ChevronRight size={18} className="text-secondary" />
    </button>
  )
}

export default TarjetaCarpeta