import { useEffect, useRef, useState } from 'react'
import { MoreVertical, Download, Eye, Users, Trash2, FolderInput } from 'lucide-react'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface TablaArchivosProps {
  archivos: Archivo[]
  archivoSeleccionadoId: string | null
  onSeleccionarArchivo: (archivo: Archivo) => void
  onVistaPrevia?: (archivo: Archivo) => void
  onDescargar: (archivo: Archivo) => void
  onCompartir?: (archivo: Archivo) => void
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
  fontWeight: 500,
  color: '#374151',
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

function TablaArchivos({
  archivos,
  archivoSeleccionadoId,
  onSeleccionarArchivo,
  onVistaPrevia,
  onDescargar,
  onCompartir,
  onEliminar,
  onMover,
  titulo = 'TODOS LOS ARCHIVOS',
}: TablaArchivosProps) {
  const [menuAbiertoId, setMenuAbiertoId] = useState<string | null>(null)
  const contenedorTablaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuAbiertoId) return
    function manejarClickFuera(evento: MouseEvent) {
      if (contenedorTablaRef.current && !contenedorTablaRef.current.contains(evento.target as Node)) {
        setMenuAbiertoId(null)
      }
    }
    function manejarEscape(evento: KeyboardEvent) {
      if (evento.key === 'Escape') setMenuAbiertoId(null)
    }
    document.addEventListener('mousedown', manejarClickFuera)
    document.addEventListener('keydown', manejarEscape)
    return () => {
      document.removeEventListener('mousedown', manejarClickFuera)
      document.removeEventListener('keydown', manejarEscape)
    }
  }, [menuAbiertoId])

  return (
    <div
      ref={contenedorTablaRef}
      style={{
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 12,
        position: 'relative',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid #F1F5F9',
          borderRadius: '12px 12px 0 0',
        }}
      >
        <p style={{ fontSize: 11, fontWeight: 700, color: '#64748B', letterSpacing: '0.07em', margin: 0 }}>
          {titulo}
        </p>
        <span style={{ fontSize: 12, color: '#94A3B8' }}>
          {archivos.length} archivo{archivos.length === 1 ? '' : 's'}
        </span>
      </div>

      {archivos.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94A3B8', fontSize: 13 }}>
          No se encontraron archivos con esos filtros.
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
              <th style={{ ...ESTILO_TH, width: '42%' }}>NOMBRE</th>
              <th style={ESTILO_TH}>FECHA DE MODIFICACIÓN</th>
              <th style={ESTILO_TH}>TAMAÑO</th>
              <th style={{ ...ESTILO_TH, textAlign: 'right' }}>ACCIONES</th>
            </tr>
          </thead>
          <tbody>
            {archivos.map((archivo, indice) => {
              const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
              const estaSeleccionado = archivo.id === archivoSeleccionadoId
              const menuAbierto = menuAbiertoId === archivo.id
              const esUltimaFila = indice === archivos.length - 1

              return (
                <tr
                  key={archivo.id}
                  onClick={() => onSeleccionarArchivo(archivo)}
                  onDoubleClick={() => {
                    if (onVistaPrevia) onVistaPrevia(archivo)
                  }}
                  style={{
                    borderBottom: esUltimaFila ? 'none' : '1px solid #F8FAFC',
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
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'flex-end',
                        gap: 6,
                        position: 'relative',
                      }}
                      onClick={(evento) => evento.stopPropagation()}
                    >
                      {onVistaPrevia && (
                        <button
                          type="button"
                          onClick={() => onVistaPrevia(archivo)}
                          title={`Vista previa de ${archivo.nombre}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '6px 10px',
                            background: '#F8FAFC',
                            border: '1px solid #E2E8F0',
                            borderRadius: 7,
                            fontSize: 12,
                            fontWeight: 600,
                            color: '#334155',
                            cursor: 'pointer',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          <Eye size={13} strokeWidth={2} />
                          Ver
                        </button>
                      )}

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
                        aria-label={`Más acciones para ${archivo.nombre}`}
                        aria-expanded={menuAbierto}
                        onClick={() => setMenuAbiertoId(menuAbierto ? null : archivo.id)}
                        style={{
                          width: 30,
                          height: 30,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: menuAbierto ? '#F1F5F9' : 'transparent',
                          border: menuAbierto ? '1px solid #CBD5E1' : '1px solid #E2E8F0',
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
                            top: 'calc(100% + 6px)',
                            background: '#FFFFFF',
                            border: '1px solid #E2E8F0',
                            borderRadius: 10,
                            boxShadow: '0 10px 28px rgba(15, 23, 42, 0.14)',
                            zIndex: 80,
                            overflow: 'hidden',
                            width: 196,
                            display: 'flex',
                            flexDirection: 'column',
                            padding: '4px 0',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              if (onVistaPrevia) {
                                onVistaPrevia(archivo)
                              } else {
                                onSeleccionarArchivo(archivo)
                              }
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <Eye size={14} strokeWidth={1.9} color="#2563EB" /> Vista previa
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              onDescargar(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <Download size={14} strokeWidth={1.9} color="#475569" /> Descargar
                          </button>
                          {onCompartir && (
                            <button
                              type="button"
                              onClick={() => {
                                onCompartir(archivo)
                                setMenuAbiertoId(null)
                              }}
                              style={ESTILO_ITEM_MENU}
                            >
                              <Users size={14} strokeWidth={1.9} color="#475569" /> Compartir
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              onMover(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={ESTILO_ITEM_MENU}
                          >
                            <FolderInput size={14} strokeWidth={1.9} color="#475569" /> Mover a carpeta
                          </button>
                          <div style={{ height: 1, background: '#F1F5F9', margin: '3px 0' }} />
                          <button
                            type="button"
                            onClick={() => {
                              onEliminar(archivo)
                              setMenuAbiertoId(null)
                            }}
                            style={{ ...ESTILO_ITEM_MENU, color: '#DC2626' }}
                          >
                            <Trash2 size={14} strokeWidth={1.9} /> Eliminar
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
