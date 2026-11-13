interface InsigniaProps {
  texto: string
  colorTexto: string
  colorFondo: string
}

/** Etiqueta pequeña de color, usada para estado, plan y tipo. */
function Insignia({ texto, colorTexto, colorFondo }: InsigniaProps) {
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: 11,
        fontWeight: 600,
        color: colorTexto,
        background: colorFondo,
        padding: '3px 10px',
        borderRadius: 20,
        whiteSpace: 'nowrap',
      }}
    >
      {texto}
    </span>
  )
}

export default Insignia