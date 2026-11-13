import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import { PLANES_LANDING } from '../../data/landing'
import type { TipoFacturacion } from '../../types/planes'
import { describirPeriodo, formatearUsd } from '../../utils/planes'

const OPCIONES: { valor: TipoFacturacion; etiqueta: string }[] = [
  { valor: 'mensual', etiqueta: 'Mensual' },
  { valor: 'anual', etiqueta: 'Anual (-20%)' },
]

function SeccionPlanes() {
  const [facturacion, setFacturacion] = useState<TipoFacturacion>('mensual')

  return (
    <section id="planes" className="lp-seccion">
      <div className="lp-contenedor">
        <div className="text-center mb-5">
          <span className="lp-etiqueta">Planes</span>
          <h2 className="lp-titulo-seccion">Un plan para cada etapa</h2>
          <p className="lp-texto-seccion mb-4">Empieza gratis y cambia de plan cuando lo necesites.</p>
          <div className="lp-selector" role="radiogroup" aria-label="Tipo de facturación">
            {OPCIONES.map((opcion) => (
              <button
                key={opcion.valor}
                type="button"
                role="radio"
                aria-checked={facturacion === opcion.valor}
                onClick={() => setFacturacion(opcion.valor)}
              >
                {opcion.etiqueta}
              </button>
            ))}
          </div>
        </div>

        <div className="row g-4 align-items-stretch pt-2">
          {PLANES_LANDING.map((plan) => {
            const precio = facturacion === 'anual' ? plan.precioAnual : plan.precioMensual
            return (
              <div key={plan.nombre} className="col-12 col-lg-4">
                <article className={`lp-plan ${plan.esPopular ? 'lp-plan-popular' : ''}`}>
                  {plan.esPopular && <span className="lp-cinta">Más popular</span>}
                  <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>{plan.nombre}</h3>
                  <p style={{ color: '#64748B', fontSize: 14 }}>{plan.almacenamiento} de almacenamiento</p>
                  <div className="mb-1">
                    <span style={{ fontSize: 44, fontWeight: 700, letterSpacing: '-0.03em' }}>${precio}</span>
                    <span style={{ color: '#64748B', fontSize: 15 }}> {describirPeriodo(facturacion)}</span>
                  </div>
                  <p style={{ fontSize: 13, color: '#16A34A', minHeight: 20 }}>
                    {facturacion === 'anual' && precio > 0 ? `Equivale a ${formatearUsd(precio / 12)} al mes` : ''}
                  </p>
                  <ul className="list-unstyled d-flex flex-column gap-2 mb-4 flex-grow-1">
                    {plan.caracteristicas.map((caracteristica) => (
                      <li key={caracteristica} className="d-flex align-items-center gap-2" style={{ fontSize: 15, color: '#334155' }}>
                        <Check size={16} strokeWidth={3} color="#2563EB" /> {caracteristica}
                      </li>
                    ))}
                  </ul>
                  <Link
                    to="/registro"
                    className={`lp-boton w-100 ${plan.esPopular ? 'lp-boton-primario' : ''}`}
                    style={plan.esPopular ? undefined : { border: '2px solid #2563EB', color: '#2563EB' }}
                  >
                    {precio === 0 ? 'Empieza gratis' : `Elegir ${plan.nombre}`}
                  </Link>
                </article>
              </div>
            )
          })}
        </div>
        <p className="text-center mt-4 mb-0" style={{ fontSize: 13, color: '#94A3B8' }}>
          Precios en dólares. Los pagos son simulados con fines académicos: no se cobra nada.
        </p>
      </div>
    </section>
  )
}

export default SeccionPlanes