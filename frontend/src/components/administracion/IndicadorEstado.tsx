import type { EstadoMiembro } from '../../types/administracion'

function IndicadorEstado({ estado }: { estado: EstadoMiembro }) {
  const estaActivo = estado === 'activo'
  const color = estaActivo ? '#16A34A' : '#D97706'

  return (
    <span className="d-inline-flex align-items-center gap-2">
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: estaActivo ? '#16A34A' : '#F59E0B', flexShrink: 0 }} />
      <span style={{ fontSize: 12, fontWeight: 500, color }}>{estaActivo ? 'Activo' : 'Invitación pendiente'}</span>
    </span>
  )
}

export default IndicadorEstado