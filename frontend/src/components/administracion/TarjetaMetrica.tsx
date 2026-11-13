import type { ReactNode } from 'react'

interface TarjetaMetricaProps {
  etiqueta: string
  valor: string
  detalle: string
  icono: ReactNode
  /** Color de acento de la barra de progreso. */
  color: string
  /** De 0 a 100. Si no se envía, no se dibuja la barra. */
  porcentaje?: number
  /** Punto verde junto al valor, usado en el estado del servicio. */
  conIndicador?: boolean
}

function TarjetaMetrica({ etiqueta, valor, detalle, icono, color, porcentaje, conIndicador = false }: TarjetaMetricaProps) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 14,
        padding: '18px 20px',
        boxShadow: '0 1px 3px rgba(15,23,42,0.04)',
        height: '100%',
      }}
    >
      <div className="d-flex align-items-center justify-content-between mb-3">
        <span style={{ fontSize: 11, fontWeight: 600, color: '#64748B', letterSpacing: '0.02em' }}>{etiqueta}</span>
        {icono}
      </div>

      <div className="d-flex align-items-center gap-2 mb-1">
        {conIndicador && (
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
        )}
        <span style={{ fontSize: 26, fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em' }}>{valor}</span>
      </div>

      <p className="mb-0" style={{ fontSize: 11, color: '#94A3B8', marginBottom: porcentaje === undefined ? 0 : 10 }}>
        {detalle}
      </p>

      {porcentaje !== undefined && (
        <div style={{ height: 4, background: '#F1F5F9', borderRadius: 2, overflow: 'hidden', marginTop: 10 }}>
          <div style={{ width: `${porcentaje}%`, height: '100%', background: color, borderRadius: 2 }} />
        </div>
      )}
    </div>
  )
}

export default TarjetaMetrica