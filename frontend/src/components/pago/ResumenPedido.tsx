import { Check } from 'lucide-react'
import type { Plan, TipoFacturacion } from '../../types/planes'
import { calcularAhorroAnual, describirPeriodo, formatearUsd, obtenerMontoPlan } from '../../utils/planes'
import { COLOR_MARCA } from '../../theme/colores'

interface ResumenPedidoProps {
  plan: Plan
  facturacion: TipoFacturacion
  deshabilitado: boolean
  onCambiarFacturacion: (facturacion: TipoFacturacion) => void
}

const OPCIONES: { valor: TipoFacturacion; etiqueta: string }[] = [
  { valor: 'mensual', etiqueta: 'Mensual' },
  { valor: 'anual', etiqueta: 'Anual · -20%' },
]

function ResumenPedido({ plan, facturacion, deshabilitado, onCambiarFacturacion }: ResumenPedidoProps) {
  const total = obtenerMontoPlan(plan, facturacion)
  const ahorro = calcularAhorroAnual(plan)

  return (
    <section style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 18, padding: 24, boxShadow: '0 1px 3px rgba(15,23,42,0.04)' }}>
      <p className="mb-1" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: '#94A3B8' }}>RESUMEN DEL PEDIDO</p>
      <div className="d-flex justify-content-between align-items-baseline gap-2 mb-3">
        <h2 className="mb-0" style={{ fontSize: 22, fontWeight: 700, color: '#0F172A' }}>Plan {plan.nombre}</h2>
        <span style={{ fontSize: 13, color: '#64748B' }}>{plan.almacenamientoLegible}</span>
      </div>

      <div role="radiogroup" aria-label="Tipo de facturación" className="d-flex p-1 mb-3" style={{ background: '#F1F5F9', borderRadius: 12 }}>
        {OPCIONES.map((opcion) => {
          const activa = opcion.valor === facturacion
          return (
            <button
              key={opcion.valor}
              type="button"
              role="radio"
              aria-checked={activa}
              disabled={deshabilitado}
              onClick={() => onCambiarFacturacion(opcion.valor)}
              className="btn flex-fill"
              style={{
                fontSize: 13,
                fontWeight: 600,
                borderRadius: 9,
                padding: '7px 10px',
                border: 'none',
                background: activa ? '#fff' : 'transparent',
                color: activa ? COLOR_MARCA : '#64748B',
                boxShadow: activa ? '0 1px 3px rgba(15,23,42,0.12)' : 'none',
              }}
            >
              {opcion.etiqueta}
            </button>
          )
        })}
      </div>

      <ul className="list-unstyled mb-3 d-flex flex-column gap-2">
        {plan.caracteristicas.map((caracteristica) => (
          <li key={caracteristica} className="d-flex align-items-center gap-2" style={{ fontSize: 13, color: '#334155' }}>
            <span className="d-flex align-items-center justify-content-center flex-shrink-0" style={{ width: 18, height: 18, borderRadius: '50%', background: 'rgba(22,163,74,0.12)' }}>
              <Check size={11} strokeWidth={3} color="#16A34A" />
            </span>
            {caracteristica}
          </li>
        ))}
      </ul>

      <div style={{ borderTop: '1px dashed #E2E8F0', paddingTop: 14 }}>
        <div className="d-flex justify-content-between mb-2" style={{ fontSize: 13, color: '#64748B' }}>
          <span>Precio {facturacion === 'anual' ? 'por 12 meses' : 'mensual'}</span>
          <span>{formatearUsd(facturacion === 'anual' ? plan.precioMensual * 12 : plan.precioMensual)}</span>
        </div>
        {facturacion === 'anual' && ahorro > 0 && (
          <div className="d-flex justify-content-between mb-2" style={{ fontSize: 13, color: '#16A34A', fontWeight: 600 }}>
            <span>Descuento anual</span>
            <span>-{formatearUsd(ahorro)}</span>
          </div>
        )}
        <div className="d-flex justify-content-between align-items-baseline mt-2">
          <span style={{ fontSize: 14, fontWeight: 600, color: '#0F172A' }}>Total a pagar</span>
          <span>
            <span style={{ fontSize: 28, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>{formatearUsd(total)}</span>
            <span style={{ fontSize: 12, color: '#64748B' }}> {describirPeriodo(facturacion)}</span>
          </span>
        </div>
        <p className="mb-0 mt-2" style={{ fontSize: 12, color: '#94A3B8' }}>
          Se renueva automáticamente. Puedes cambiar de plan cuando quieras.
        </p>
      </div>
    </section>
  )
}

export default ResumenPedido