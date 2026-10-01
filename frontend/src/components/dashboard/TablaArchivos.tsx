import { MoreVertical, Download } from 'lucide-react'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface TablaArchivosProps {
  archivos: Archivo[]
  archivoSeleccionadoId: string | null
  onSeleccionarArchivo: (archivo: Archivo) => void
}

const ESTILO_TH: React.CSSProperties = {
  padding: '10px 14px',
  fontSize: 11,
  fontWeight: 600,
  color: '#64748B',
  letterSpacing: '0.05em',
  background: '#F8FAFC',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

function TablaArchivos({ archivos, archivoSeleccionadoId, onSeleccionarArchivo }: TablaArchivosProps) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid #F1F5F9',
        }}
      >
        <p style={{ fontSize: 11, fontWeight: 700, color: '#64748B', letterSpacing: '0.07em', margin: 0 }}>
          TODOS LOS ARCHIVOS
        </p>
        <span style={{ fontSize: 12, color: '#94A3B8' }}>Actualizado hace 2 min</span>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
            <th style={{ ...ESTILO_TH, width: '44%' }}>NOMBRE</th>
            <th style={ESTILO_TH}>FECHA DE MODIFICACIÓN</th>
            <th style={ESTILO_TH}>TAMAÑO</th>
            <th style={{ ...ESTILO_TH, textAlign: 'right' }}>ACCIONES</th>
          </tr>
        </thead>
        <tbody>
          {archivos.map((archivo) => {
            const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
            const estaSeleccionado = archivo.id === archivoSeleccionadoId

            return (
              <tr
                key={archivo.id}
                onClick={() => onSeleccionarArchivo(archivo)}
                style={{
                  borderBottom: '1px solid #F8FAFC',
                  background: estaSeleccionado ? 'rgba(37,99,235,0.04)' : 'transparent',
                  cursor: 'pointer',
                }}
              >
                <td style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        backgroundColor: configuracion.colorFondo,
                        color: configuracion.colorTexto,
                        borderRadius: 6,
                        fontSize: 11,
                        padding: '3px 6px',
                      }}
                    >
                      {configuracion.etiqueta}
                    </span>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: '#0F172A',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: 220,
                        display: 'block',
                      }}
                    >
                      {archivo.nombre}
                    </span>
                    {archivo.esNuevo && (
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#2563EB', flexShrink: 0 }} />
                    )}
                  </div>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <span style={{ fontSize: 12, color: '#64748B' }}>{archivo.fechaModificacion}</span>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <span style={{ fontSize: 12, color: '#64748B' }}>{archivo.tamano}</span>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <div
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}
                    onClick={(evento) => evento.stopPropagation()}
                  >
                    <button
                      type="button"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '6px 11px',
                        background: '#EFF6FF',
                        border: '1px solid #BFDBFE',
                        borderRadius: 7,
                        fontSize: 12,
                        fontWeight: 600,
                        color: '#2563EB',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <Download size={12} strokeWidth={2.2} />
                      Descargar
                    </button>
                    <button
                      type="button"
                      style={{
                        width: 30,
                        height: 30,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'transparent',
                        border: '1px solid #E2E8F0',
                        borderRadius: 7,
                        cursor: 'pointer',
                        color: '#64748B',
                      }}
                    >
                      <MoreVertical size={14} strokeWidth={2} />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default TablaArchivos