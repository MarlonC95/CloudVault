import type { ReactNode } from 'react'

export interface ColumnaTabla<Fila> {
  encabezado: string
  alinearDerecha?: boolean
  renderizar: (fila: Fila) => ReactNode
}

interface TablaDatosProps<Fila> {
  columnas: ColumnaTabla<Fila>[]
  filas: Fila[]
  obtenerClave: (fila: Fila) => string
  mensajeVacio: string
  anchoMinimo?: number
}

/** Tabla genérica: cada pantalla solo decide qué columnas quiere y cómo se dibuja cada celda. */
function TablaDatos<Fila>({ columnas, filas, obtenerClave, mensajeVacio, anchoMinimo = 640 }: TablaDatosProps<Fila>) {
  if (filas.length === 0) {
    return (
      <p className="text-center mb-0" style={{ padding: '32px 20px', fontSize: 13, color: '#94A3B8' }}>
        {mensajeVacio}
      </p>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="w-100" style={{ borderCollapse: 'collapse', minWidth: anchoMinimo }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #E2E8F0', background: '#F8FAFC' }}>
            {columnas.map((columna) => (
              <th
                key={columna.encabezado}
                style={{
                  padding: '10px 20px',
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#94A3B8',
                  letterSpacing: '0.06em',
                  textAlign: columna.alinearDerecha ? 'right' : 'left',
                }}
              >
                {columna.encabezado.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={obtenerClave(fila)} style={{ borderBottom: indice < filas.length - 1 ? '1px solid #F1F5F9' : 'none' }}>
              {columnas.map((columna) => (
                <td
                  key={columna.encabezado}
                  style={{ padding: '14px 20px', verticalAlign: 'middle', textAlign: columna.alinearDerecha ? 'right' : 'left' }}
                >
                  {columna.renderizar(fila)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default TablaDatos