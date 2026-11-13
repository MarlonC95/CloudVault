import { useState } from 'react'
import { ChevronRight, Clock, Download, MonitorUp, Shield, Trash2 } from 'lucide-react'
import type { EventoAuditoria, TipoEvento } from '../../types/administracion'
import { formatearFechaRelativa } from '../../utils/fechas'
import { obtenerColoresSeveridad } from '../../utils/administracion'

const EVENTOS_VISIBLES_INICIALMENTE = 3

const ICONOS_POR_TIPO: Record<TipoEvento, typeof Shield> = {
  subida: MonitorUp,
  eliminacion: Trash2,
  seguridad: Shield,
}

interface PanelAuditoriaProps {
  eventos: EventoAuditoria[]
  onExportar: () => void
}

function PanelAuditoria({ eventos, onExportar }: PanelAuditoriaProps) {
  const [mostrarTodos, setMostrarTodos] = useState(false)
  const eventosVisibles = mostrarTodos ? eventos : eventos.slice(0, EVENTOS_VISIBLES_INICIALMENTE)
  const hayMasEventos = eventos.length > EVENTOS_VISIBLES_INICIALMENTE

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
      <header className="d-flex align-items-center justify-content-between gap-2" style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0' }}>
        <div>
          <h2 className="mb-1" style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Registros de auditoría recientes</h2>
          <p className="mb-0" style={{ fontSize: 12, color: '#94A3B8' }}>Últimas actividades de la organización</p>
        </div>
        <button
          type="button"
          onClick={onExportar}
          disabled={eventos.length === 0}
          className="btn d-flex align-items-center gap-1 flex-shrink-0"
          style={{ border: '1px solid #E2E8F0', borderRadius: 8, padding: '6px 11px', fontSize: 11, fontWeight: 500, color: '#64748B' }}
        >
          <Download size={12} strokeWidth={1.9} />
          Exportar
        </button>
      </header>

      {eventos.length === 0 ? (
        <p className="text-center mb-0" style={{ padding: '32px 20px', fontSize: 13, color: '#94A3B8' }}>
          Todavía no hay actividad registrada.
        </p>
      ) : (
        <ul className="list-unstyled mb-0" style={{ padding: '8px 0' }}>
          {eventosVisibles.map((evento, indice) => {
            const colores = obtenerColoresSeveridad(evento.severidad)
            const Icono = ICONOS_POR_TIPO[evento.tipo]
            return (
              <li
                key={evento.id}
                className="d-flex align-items-start gap-3"
                style={{ padding: '14px 20px', borderBottom: indice < eventosVisibles.length - 1 ? '1px solid #F1F5F9' : 'none' }}
              >
                <div
                  className="d-flex align-items-center justify-content-center flex-shrink-0"
                  style={{ width: 32, height: 32, borderRadius: 8, background: colores.fondo, color: colores.texto }}
                >
                  <Icono size={14} strokeWidth={1.8} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p className="mb-1" style={{ fontSize: 13, color: '#0F172A', fontWeight: 500, lineHeight: 1.45, wordBreak: 'break-word' }}>
                    {evento.descripcion}
                  </p>
                  <div className="d-flex align-items-center gap-2">
                    <Clock size={11} color="#94A3B8" strokeWidth={1.8} />
                    <span style={{ fontSize: 11, color: '#94A3B8' }}>{formatearFechaRelativa(evento.fecha)}</span>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        color: colores.texto,
                        background: colores.fondo,
                        padding: '1px 6px',
                        borderRadius: 4,
                        letterSpacing: '0.06em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {colores.etiqueta}
                    </span>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {hayMasEventos && (
        <footer className="d-flex justify-content-center" style={{ padding: '12px 20px', borderTop: '1px solid #F1F5F9' }}>
          <button
            type="button"
            onClick={() => setMostrarTodos((valorActual) => !valorActual)}
            className="btn d-flex align-items-center gap-1"
            style={{ fontSize: 12, fontWeight: 600, color: '#2563EB', padding: 0 }}
          >
            {mostrarTodos ? 'Ver menos' : 'Ver registro completo'}
            <ChevronRight size={13} strokeWidth={2} style={{ transform: mostrarTodos ? 'rotate(-90deg)' : 'none' }} />
          </button>
        </footer>
      )}
    </section>
  )
}

export default PanelAuditoria