interface FilaProporcionProps {
  etiqueta: string
  valor: string
  /** De 0 a 100. */
  porcentaje: number
  color: string
}

/** Una línea con nombre, valor y una barra proporcional (planes y almacenamiento por tipo). */
function FilaProporcion({ etiqueta, valor, porcentaje, color }: FilaProporcionProps) {
  return (
    <div className="mb-3">
      <div className="d-flex justify-content-between gap-2 mb-1">
        <span style={{ fontSize: 12, fontWeight: 600, color: '#0F172A' }}>{etiqueta}</span>
        <span style={{ fontSize: 12, color: '#64748B' }}>{valor}</span>
      </div>
      <div
        role="progressbar"
        aria-label={etiqueta}
        aria-valuenow={porcentaje}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{ height: 6, background: '#F1F5F9', borderRadius: 3, overflow: 'hidden' }}
      >
        <div style={{ width: `${porcentaje}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
    </div>
  )
}

export default FilaProporcion