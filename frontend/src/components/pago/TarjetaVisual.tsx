import type { CSSProperties } from 'react'
import type { DatosTarjeta } from '../../types/pago'
import { detectarMarca, formatearNumeroTarjeta, obtenerNombreMarca } from '../../utils/tarjeta'

interface TarjetaVisualProps {
  datos: DatosTarjeta
  /** Muestra el reverso cuando se escribe el código de seguridad. */
  mostrarReverso: boolean
}

const CARA_BASE: CSSProperties = {
  position: 'absolute',
  inset: 0,
  borderRadius: 18,
  padding: '22px 24px',
  color: '#fff',
  backfaceVisibility: 'hidden',
  WebkitBackfaceVisibility: 'hidden',
  background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%)',
  boxShadow: '0 18px 40px rgba(37, 99, 235, 0.28)',
  overflow: 'hidden',
}

const ETIQUETA: CSSProperties = { fontSize: 9, letterSpacing: '0.12em', opacity: 0.65, textTransform: 'uppercase' }

/** Vista previa de la tarjeta que se actualiza mientras se escribe. Es solo decorativa. */
function TarjetaVisual({ datos, mostrarReverso }: TarjetaVisualProps) {
  const marca = detectarMarca(datos.numero)
  const numeroMostrado = formatearNumeroTarjeta(datos.numero) || '•••• •••• •••• ••••'

  return (
    <div aria-hidden="true" style={{ perspective: 1200, width: '100%', maxWidth: 380, margin: '0 auto' }}>
      <div
        style={{
          position: 'relative',
          aspectRatio: '1.586',
          transition: 'transform 0.6s ease',
          transformStyle: 'preserve-3d',
          transform: mostrarReverso ? 'rotateY(180deg)' : 'none',
        }}
      >
        {/* Frente */}
        <div style={CARA_BASE}>
          <div style={{ position: 'absolute', width: 220, height: 220, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', top: -90, right: -60 }} />
          <div style={{ position: 'absolute', width: 160, height: 160, borderRadius: '50%', background: 'rgba(255,255,255,0.05)', bottom: -70, left: -40 }} />
          <div className="d-flex justify-content-between align-items-start" style={{ position: 'relative' }}>
            <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: '0.02em' }}>CloudVault</span>
            <span style={{ fontWeight: 700, fontSize: 13, fontStyle: 'italic', opacity: 0.9 }}>{obtenerNombreMarca(marca)}</span>
          </div>
          <div
            style={{
              position: 'relative',
              width: 42,
              height: 30,
              borderRadius: 6,
              marginTop: 18,
              background: 'linear-gradient(135deg, #FDE68A, #D97706)',
            }}
          />
          <p className="mb-0" style={{ position: 'relative', marginTop: 16, fontSize: 'clamp(15px, 4.6vw, 20px)', letterSpacing: '0.12em', fontFamily: 'monospace' }}>
            {numeroMostrado}
          </p>
          <div className="d-flex justify-content-between align-items-end" style={{ position: 'absolute', left: 24, right: 24, bottom: 20 }}>
            <div style={{ minWidth: 0 }}>
              <div style={ETIQUETA}>Titular</div>
              <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'uppercase', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 220 }}>
                {datos.titular.trim() || 'Nombre Apellido'}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={ETIQUETA}>Vence</div>
              <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace' }}>{datos.vencimiento || 'MM/AA'}</div>
            </div>
          </div>
        </div>

        {/* Reverso */}
        <div style={{ ...CARA_BASE, padding: 0, transform: 'rotateY(180deg)' }}>
          <div style={{ height: 42, background: '#020617', marginTop: 26 }} />
          <div className="d-flex align-items-center gap-2" style={{ padding: '18px 24px 0' }}>
            <div style={{ flex: 1, height: 34, borderRadius: 6, background: 'repeating-linear-gradient(90deg, #E2E8F0 0 8px, #CBD5E1 8px 16px)' }} />
            <div style={{ width: 64, height: 34, borderRadius: 6, background: '#fff', color: '#0F172A', fontFamily: 'monospace', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {datos.cvv || '•••'}
            </div>
          </div>
          <p className="mb-0" style={{ padding: '14px 24px', fontSize: 10, opacity: 0.6 }}>
            Tarjeta de simulación. CloudVault no procesa pagos reales.
          </p>
        </div>
      </div>
    </div>
  )
}

export default TarjetaVisual