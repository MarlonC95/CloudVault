import { FlaskConical } from 'lucide-react'
import { TARJETA_PRUEBA_APROBADA, TARJETA_PRUEBA_RECHAZADA } from '../../utils/tarjeta'

interface AvisoSimulacionProps {
  deshabilitado: boolean
  onUsarTarjeta: (numero: string) => void
}

const TARJETAS = [
  { numero: TARJETA_PRUEBA_APROBADA, resultado: 'Pago aprobado', color: '#16A34A' },
  { numero: TARJETA_PRUEBA_RECHAZADA, resultado: 'Pago rechazado', color: '#DC2626' },
]

/** Explica que el pago es simulado y ofrece las tarjetas de prueba. */
function AvisoSimulacion({ deshabilitado, onUsarTarjeta }: AvisoSimulacionProps) {
  return (
    <section style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 16, padding: 18 }}>
      <div className="d-flex align-items-center gap-2 mb-2">
        <FlaskConical size={16} color="#B45309" />
        <h3 className="mb-0" style={{ fontSize: 14, fontWeight: 700, color: '#92400E' }}>Pago simulado</h3>
      </div>
      <p className="mb-3" style={{ fontSize: 12.5, color: '#92400E', lineHeight: 1.5 }}>
        No se cobra nada y los datos de la tarjeta no salen de tu navegador. Usa una tarjeta de prueba con cualquier
        nombre, una fecha futura y cualquier código.
      </p>
      <div className="d-flex flex-column gap-2">
        {TARJETAS.map((tarjeta) => (
          <button
            key={tarjeta.numero}
            type="button"
            disabled={deshabilitado}
            onClick={() => onUsarTarjeta(tarjeta.numero)}
            className="btn d-flex justify-content-between align-items-center"
            style={{ background: '#fff', border: '1px solid #FDE68A', borderRadius: 10, padding: '8px 12px', fontSize: 12.5 }}
          >
            <span style={{ fontFamily: 'monospace', color: '#0F172A' }}>{tarjeta.numero}</span>
            <span style={{ fontWeight: 600, color: tarjeta.color }}>{tarjeta.resultado} · Usar</span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default AvisoSimulacion