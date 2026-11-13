import { useState } from 'react'
import { Download } from 'lucide-react'
import type { EventoPlataforma } from '../../types/plataforma'
import { formatearFechaRelativa } from '../../utils/fechas'
import { describirDetalles, filtrarEventos, obtenerAccionesDisponibles } from '../../utils/plataforma'
import CampoBusqueda from './CampoBusqueda'
import ContenedorPanel from './ContenedorPanel'
import TablaDatos, { type ColumnaTabla } from './TablaDatos'

const COLUMNAS: ColumnaTabla<EventoPlataforma>[] = [
  {
    encabezado: 'Fecha',
    renderizar: (evento) => <span style={{ fontSize: 12, color: '#64748B', whiteSpace: 'nowrap' }}>{formatearFechaRelativa(evento.fechaEvento)}</span>,
  },
  {
    encabezado: 'Acción',
    renderizar: (evento) => (
      <code style={{ fontSize: 11, fontWeight: 600, color: '#0F172A', background: '#F1F5F9', padding: '3px 8px', borderRadius: 6 }}>
        {evento.accion}
      </code>
    ),
  },
  { encabezado: 'Usuario', renderizar: (evento) => <span style={{ fontSize: 13 }}>{evento.usuarioNombre ?? '—'}</span> },
  { encabezado: 'Organización', renderizar: (evento) => <span style={{ fontSize: 13 }}>{evento.organizacionNombre ?? '—'}</span> },
  { encabezado: 'Detalles', renderizar: (evento) => <span style={{ fontSize: 12, color: '#64748B', wordBreak: 'break-word' }}>{describirDetalles(evento.detalles)}</span> },
]

interface PanelAuditoriaPlataformaProps {
  eventos: EventoPlataforma[]
  onExportar: (eventos: EventoPlataforma[]) => void
}

function PanelAuditoriaPlataforma({ eventos, onExportar }: PanelAuditoriaPlataformaProps) {
  const [busqueda, setBusqueda] = useState('')
  const [accion, setAccion] = useState('')
  const eventosVisibles = filtrarEventos(eventos, busqueda, accion)

  return (
    <ContenedorPanel
      titulo="Auditoría de la plataforma"
      subtitulo={`${eventosVisibles.length} de ${eventos.length} eventos, del más reciente al más antiguo`}
      acciones={
        <button
          type="button"
          onClick={() => onExportar(eventosVisibles)}
          disabled={eventosVisibles.length === 0}
          className="btn d-flex align-items-center gap-1"
          style={{ border: '1px solid #E2E8F0', borderRadius: 8, padding: '6px 11px', fontSize: 11, fontWeight: 500, color: '#64748B' }}
        >
          <Download size={12} strokeWidth={1.9} />
          Exportar
        </button>
      }
    >
      <div className="d-flex flex-wrap gap-2" style={{ padding: '14px 20px', borderBottom: '1px solid #F1F5F9' }}>
        <CampoBusqueda valor={busqueda} onCambiar={setBusqueda} placeholder="Buscar en el registro" etiqueta="Buscar eventos" />
        <select
          aria-label="Filtrar por acción"
          value={accion}
          onChange={(evento) => setAccion(evento.target.value)}
          className="form-select"
          style={{ maxWidth: 240, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, fontSize: 13 }}
        >
          <option value="">Todas las acciones</option>
          {obtenerAccionesDisponibles(eventos).map((codigo) => (
            <option key={codigo} value={codigo}>
              {codigo}
            </option>
          ))}
        </select>
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        filas={eventosVisibles}
        obtenerClave={(evento) => evento.id}
        mensajeVacio="Ningún evento coincide con los filtros."
        anchoMinimo={760}
      />
    </ContenedorPanel>
  )
}

export default PanelAuditoriaPlataforma