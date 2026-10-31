import type { RolMiembro } from '../../types/administracion'
import { obtenerColoresRol, obtenerEtiquetaRol } from '../../utils/administracion'

function InsigniaRol({ rol }: { rol: RolMiembro }) {
  const colores = obtenerColoresRol(rol)
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: 11,
        fontWeight: 600,
        color: colores.texto,
        background: colores.fondo,
        padding: '3px 9px',
        borderRadius: 6,
        whiteSpace: 'nowrap',
      }}
    >
      {obtenerEtiquetaRol(rol)}
    </span>
  )
}

export default InsigniaRol