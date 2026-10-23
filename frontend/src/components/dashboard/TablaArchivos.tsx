import { useState } from 'react'
import { MoreVertical, Download, Eye, Users, Trash2, FolderInput } from 'lucide-react'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface TablaArchivosProps {
  archivos: Archivo[]
  archivoSeleccionadoId: string | null
  onSeleccionarArchivo: (archivo: Archivo) => void
  onDescargar: (archivo: Archivo) => void
  onCompartir: (archivo: Archivo) => void
  onEliminar: (archivo: Archivo) => void
  onMover: (archivo: Archivo) => void
  titulo?: string
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

const ESTILO_ITEM_MENU: React.CSSProperties = {
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  gap: 9,
  padding: '10px 14px',
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontSize: 13,
  color: '#374151',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

function TablaArchivos({
  archivos,
  archivoSeleccionadoId,
  onSeleccionarArchivo,
  onDescargar,
  onCompartir,
  onEliminar,
  onMover,
  titulo = 'TODOS LOS ARCHIVOS',
}: TablaArchivosProps) {
  const [menuAbiertoId, setMenuAbiertoId] = useState<string | null>(null)

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
          {titulo}
        </p>
        <span style={{ fontSize: 12, color: '#94A3B8' }}>{archivos.length} archivo{archivos.length === 1 ? '' : 's'}</span>
      </div>

      {archivos.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94A3B8', fontSize: 13 }}>
          No se encontraron archivos con esos filtros.
        </div>
      ) : (
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
              const menuAbierto = menuAbiertoId === archivo.id

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
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6, position: 'relative' }}
                      onClick={(evento) => evento.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() => onDescargar(archivo)}
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
                        onClick={() => setMenuAbiertoId(menuAbierto ? null : archivo.id)}
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

                      {menuAbierto && (
                        <div
                          style={{
                            position: 'absolute',
                            right: 0,
                            top: 'calc(100% + 4px)',
                            background: '#fff',
                            border: '1px solid #E2E8F0',
                            borderRadius: 9,
                            boxShadow: '0 4px 16px rgba(15,23,42,0.10)',
                            zIndex: 60,
                            overflow: 'hidden',
                            width: 190,
                            display: 'flex',
                            flexDirection: 'column',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              onSeleccionarArchivo(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <Eye size={13} strokeWidth={1.9} /> Vista previa
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              onCompartir(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <Users size={13} strokeWidth={1.9} /> Compartir
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              onMover(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <FolderInput size={13} strokeWidth={1.9} /> Mover a carpeta
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              onEliminar(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={{ ...ESTILO_ITEM_MENU, color: '#DC2626' }}
                          >
                            <Trash2 size={13} strokeWidth={1.9} /> Eliminar
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default TablaArchivos
