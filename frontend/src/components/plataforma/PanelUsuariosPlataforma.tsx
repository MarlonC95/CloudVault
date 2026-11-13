import { useState } from 'react'
import type { UsuarioPlataforma } from '../../types/plataforma'
import { obtenerIniciales } from '../../utils/administracion'
import { formatearFechaCorta } from '../../utils/fechas'
import { filtrarUsuarios } from '../../utils/plataforma'
import { COLOR_NAVY } from '../../theme/colores'
import CampoBusqueda from './CampoBusqueda'
import ContenedorPanel from './ContenedorPanel'
import Insignia from './Insignia'
import TablaDatos, { type ColumnaTabla } from './TablaDatos'

interface PanelUsuariosPlataformaProps {
  usuarios: UsuarioPlataforma[]
  /** Correo de quien tiene la sesión abierta: esa cuenta no puede deshabilitarse a sí misma. */
  correoUsuarioActual?: string
  onCambiarEstado: (usuario: UsuarioPlataforma) => void
}

function PanelUsuariosPlataforma({ usuarios, correoUsuarioActual, onCambiarEstado }: PanelUsuariosPlataformaProps) {
  const [busqueda, setBusqueda] = useState('')
  const usuariosVisibles = filtrarUsuarios(usuarios, busqueda)

  function esCuentaPropia(usuario: UsuarioPlataforma): boolean {
    return usuario.correoElectronico.toLowerCase() === correoUsuarioActual?.toLowerCase()
  }

  const columnas: ColumnaTabla<UsuarioPlataforma>[] = [
    {
      encabezado: 'Usuario',
      renderizar: (usuario) => (
        <div className="d-flex align-items-center gap-2" style={{ opacity: usuario.estaActivo ? 1 : 0.6 }}>
          <div
            className="d-flex align-items-center justify-content-center flex-shrink-0"
            style={{ width: 34, height: 34, borderRadius: '50%', background: COLOR_NAVY, color: '#fff', fontWeight: 700, fontSize: 12 }}
          >
            {obtenerIniciales(usuario.nombreCompleto)}
          </div>
          <div style={{ minWidth: 0 }}>
            <p className="mb-0" style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{usuario.nombreCompleto}</p>
            <p className="mb-0" style={{ fontSize: 11, color: '#94A3B8' }}>{usuario.correoElectronico}</p>
          </div>
        </div>
      ),
    },
    { encabezado: 'Organizaciones', renderizar: (usuario) => <span style={{ fontSize: 13 }}>{usuario.organizacionesCount}</span> },
    { encabezado: 'Almacenamiento', renderizar: (usuario) => <span style={{ fontSize: 13 }}>{usuario.almacenamientoPropietarioLegible}</span> },
    { encabezado: 'Registro', renderizar: (usuario) => <span style={{ fontSize: 12, color: '#64748B' }}>{formatearFechaCorta(usuario.fechaRegistro)}</span> },
    {
      encabezado: 'Estado',
      renderizar: (usuario) =>
        usuario.estaActivo ? (
          <Insignia texto="Habilitada" colorTexto="#16A34A" colorFondo="rgba(22,163,74,0.08)" />
        ) : (
          <Insignia texto="Deshabilitada" colorTexto="#DC2626" colorFondo="rgba(220,38,38,0.08)" />
        ),
    },
    {
      encabezado: 'Acciones',
      alinearDerecha: true,
      renderizar: (usuario) => {
        const noSePuedeDeshabilitar = usuario.estaActivo && esCuentaPropia(usuario)
        const color = usuario.estaActivo ? '#DC2626' : '#16A34A'
        return (
          <button
            type="button"
            onClick={() => onCambiarEstado(usuario)}
            disabled={noSePuedeDeshabilitar}
            title={noSePuedeDeshabilitar ? 'No puedes deshabilitar tu propia cuenta' : undefined}
            className="btn"
            style={{ fontSize: 11, fontWeight: 600, borderRadius: 8, padding: '5px 12px', color, border: `1px solid ${color}33`, background: `${color}12` }}
          >
            {usuario.estaActivo ? 'Deshabilitar' : 'Habilitar'}
          </button>
        )
      },
    },
  ]

  return (
    <ContenedorPanel
      titulo="Usuarios de la plataforma"
      subtitulo={`${usuariosVisibles.length} de ${usuarios.length} cuentas`}
      acciones={<CampoBusqueda valor={busqueda} onCambiar={setBusqueda} placeholder="Buscar por nombre o correo" etiqueta="Buscar usuarios" />}
    >
      <TablaDatos
        columnas={columnas}
        filas={usuariosVisibles}
        obtenerClave={(usuario) => usuario.id}
        mensajeVacio="Ningún usuario coincide con la búsqueda."
        anchoMinimo={760}
      />
    </ContenedorPanel>
  )
}

export default PanelUsuariosPlataforma