import type { ReactNode } from 'react'

interface ContenedorPanelProps {
  titulo: string
  subtitulo?: string
  /** Controles a la derecha del encabezado (buscador, botón de exportar, etc.). */
  acciones?: ReactNode
  children: ReactNode
}

/** Tarjeta blanca con encabezado, igual a las del resto de Administración. */
function ContenedorPanel({ titulo, subtitulo, acciones, children }: ContenedorPanelProps) {
  return (
    <section
      style={{
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 14,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(15,23,42,0.04)',
      }}
    >
      <header
        className="d-flex align-items-center justify-content-between flex-wrap gap-2"
        style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0' }}
      >
        <div>
          <h2 className="mb-1" style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{titulo}</h2>
          {subtitulo && <p className="mb-0" style={{ fontSize: 12, color: '#94A3B8' }}>{subtitulo}</p>}
        </div>
        {acciones}
      </header>
      {children}
    </section>
  )
}

export default ContenedorPanel