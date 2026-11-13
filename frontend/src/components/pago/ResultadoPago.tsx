import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'

interface FilaComprobante {
  etiqueta: string
  valor: string
}

interface ResultadoPagoProps {
  aprobado: boolean
  titulo: string
  mensaje: string
  filas?: FilaComprobante[]
  /** Botón principal; en el rechazo vuelve al formulario. */
  accionPrincipal: ReactNode
}

/** Pantalla final del pago: comprobante si se aprobó, o motivo y reintento si se rechazó. */
function ResultadoPago({ aprobado, titulo, mensaje, filas = [], accionPrincipal }: ResultadoPagoProps) {
  const color = aprobado ? '#16A34A' : '#DC2626'
  const Icono = aprobado ? CheckCircle2 : XCircle

  return (
    <section
      role="status"
      className="mx-auto text-center"
      style={{ maxWidth: 520, background: '#fff', border: '1px solid #E2E8F0', borderRadius: 22, padding: '36px 28px', boxShadow: '0 10px 30px rgba(15,23,42,0.06)' }}
    >
      <div
        className="d-inline-flex align-items-center justify-content-center mb-3"
        style={{ width: 72, height: 72, borderRadius: '50%', background: `${color}14` }}
      >
        <Icono size={40} color={color} strokeWidth={1.8} />
      </div>
      <h1 style={{ fontSize: 26, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em' }}>{titulo}</h1>
      <p className="mb-4" style={{ fontSize: 14, color: '#64748B', lineHeight: 1.55 }}>{mensaje}</p>

      {filas.length > 0 && (
        <dl className="text-start mb-4" style={{ background: '#F8FAFC', borderRadius: 14, padding: '6px 18px' }}>
          {filas.map((fila, indice) => (
            <div
              key={fila.etiqueta}
              className="d-flex justify-content-between gap-3"
              style={{ padding: '10px 0', borderBottom: indice < filas.length - 1 ? '1px solid #E2E8F0' : 'none', fontSize: 13 }}
            >
              <dt style={{ fontWeight: 500, color: '#64748B' }}>{fila.etiqueta}</dt>
              <dd className="mb-0 text-end" style={{ fontWeight: 600, color: '#0F172A' }}>{fila.valor}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="d-flex flex-column flex-sm-row gap-2 justify-content-center">
        {accionPrincipal}
        <Link
          to="/planes"
          className="btn fw-semibold"
          style={{ border: '1px solid #E2E8F0', borderRadius: 50, padding: '10px 22px', color: COLOR_MARCA }}
        >
          Volver a planes
        </Link>
      </div>
    </section>
  )
}

export default ResultadoPago