import { useState } from 'react'
import type { OrganizacionPlataforma } from '../../types/plataforma'
import { formatearFechaCorta } from '../../utils/fechas'
import { filtrarOrganizaciones, obtenerColorPlan, obtenerEtiquetaPlan } from '../../utils/plataforma'
import CampoBusqueda from './CampoBusqueda'
import ContenedorPanel from './ContenedorPanel'
import Insignia from './Insignia'
import TablaDatos, { type ColumnaTabla } from './TablaDatos'

const COLUMNAS: ColumnaTabla<OrganizacionPlataforma>[] = [
  {
    encabezado: 'Organización',
    renderizar: (organizacion) => <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{organizacion.nombre}</span>,
  },
  {
    encabezado: 'Tipo',
    renderizar: (organizacion) =>
      organizacion.tipo === 'PERSONAL' ? (
        <Insignia texto="Personal" colorTexto="#475569" colorFondo="rgba(100,116,139,0.1)" />
      ) : (
        <Insignia texto="Compartida" colorTexto="#2563EB" colorFondo="rgba(37,99,235,0.08)" />
      ),
  },
  {
    encabezado: 'Plan',
    renderizar: (organizacion) => (
      <span style={{ fontSize: 13, fontWeight: 600, color: obtenerColorPlan(organizacion.plan) }}>
        {obtenerEtiquetaPlan(organizacion.plan)}
      </span>
    ),
  },
  { encabezado: 'Almacenamiento', renderizar: (organizacion) => <span style={{ fontSize: 13 }}>{organizacion.almacenamientoUsadoLegible}</span> },
  {
    encabezado: 'Creación',
    renderizar: (organizacion) => <span style={{ fontSize: 12, color: '#64748B' }}>{formatearFechaCorta(organizacion.fechaCreacion)}</span>,
  },
]

interface PanelOrganizacionesPlataformaProps {
  organizaciones: OrganizacionPlataforma[]
}

function PanelOrganizacionesPlataforma({ organizaciones }: PanelOrganizacionesPlataformaProps) {
  const [busqueda, setBusqueda] = useState('')
  const organizacionesVisibles = filtrarOrganizaciones(organizaciones, busqueda)

  return (
    <ContenedorPanel
      titulo="Catálogo de organizaciones"
      subtitulo={`${organizacionesVisibles.length} de ${organizaciones.length} organizaciones`}
      acciones={<CampoBusqueda valor={busqueda} onCambiar={setBusqueda} placeholder="Buscar por nombre" etiqueta="Buscar organizaciones" />}
    >
      <TablaDatos
        columnas={COLUMNAS}
        filas={organizacionesVisibles}
        obtenerClave={(organizacion) => organizacion.id}
        mensajeVacio="Ninguna organización coincide con la búsqueda."
      />
    </ContenedorPanel>
  )
}

export default PanelOrganizacionesPlataforma