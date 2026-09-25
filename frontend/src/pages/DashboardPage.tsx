import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Cloud,
  Upload,
  HardDrive,
  Users,
  Clock,
  Trash2,
  Zap,
  Shield,
  LogOut,
} from 'lucide-react'
import { cerrarSesion, obtenerSesion } from '../services/authService'

type SeccionExplorador = 'mi-unidad' | 'compartidos' | 'recientes' | 'papelera' | 'planes' | 'administracion'

const COLOR_MARCA = '#2563EB'
const COLOR_NAVY = '#0F172A'

interface ElementoMenu {
  id: SeccionExplorador
  etiqueta: string
  icono: React.ReactNode
}

const ELEMENTOS_EXPLORADOR: ElementoMenu[] = [
  { id: 'mi-unidad', etiqueta: 'Mi Unidad', icono: <HardDrive size={18} /> },
  { id: 'compartidos', etiqueta: 'Compartidos conmigo', icono: <Users size={18} /> },
  { id: 'recientes', etiqueta: 'Recientes', icono: <Clock size={18} /> },
]

const ELEMENTOS_GESTION: ElementoMenu[] = [
  { id: 'papelera', etiqueta: 'Papelera', icono: <Trash2 size={18} /> },
  { id: 'planes', etiqueta: 'Planes', icono: <Zap size={18} /> },
  { id: 'administracion', etiqueta: 'Administración', icono: <Shield size={18} /> },
]

function DashboardPage() {
  const [seccionActiva, setSeccionActiva] = useState<SeccionExplorador>('mi-unidad')
  const navegar = useNavigate()
  const usuario = obtenerSesion()?.usuario

  function manejarSalida() {
    cerrarSesion()
    navegar('/login', { replace: true })
  }

  // TODO: reemplazar por datos reales del plan del usuario cuando exista la API
  const almacenamientoUsadoGb = 45
  const almacenamientoTotalGb = 100
  const porcentajeUsado = (almacenamientoUsadoGb / almacenamientoTotalGb) * 100

  function renderizarBotonMenu(elemento: ElementoMenu) {
    const estaActivo = seccionActiva === elemento.id
    return (
      <button
        key={elemento.id}
        type="button"
        className="btn d-flex align-items-center gap-2 w-100 text-start mb-1 border-0"
        style={{
          backgroundColor: estaActivo ? 'rgba(255,255,255,0.1)' : 'transparent',
          color: estaActivo ? '#FFFFFF' : 'rgba(255,255,255,0.7)',
          borderRadius: '10px',
          padding: '10px 14px',
        }}
        onClick={() => setSeccionActiva(elemento.id)}
      >
        {elemento.icono}
        <span className="small fw-medium">{elemento.etiqueta}</span>
      </button>
    )
  }

  return (
    <div className="d-flex" style={{ minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside
        className="d-none d-lg-flex flex-column p-3 text-white flex-shrink-0"
        style={{ width: '260px', backgroundColor: COLOR_NAVY }}
      >
        <div className="d-flex align-items-center gap-2 mb-4 px-2">
          <Cloud size={26} color={COLOR_MARCA} />
          <span className="fw-bold fs-5">CloudVault PaaS</span>
        </div>

        <button
          type="button"
          className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold mb-4"
          style={{ backgroundColor: COLOR_MARCA, borderRadius: '10px', padding: '10px' }}
        >
          <Upload size={18} />
          Subir Archivo
        </button>

        <div className="text-uppercase small fw-semibold px-2 mb-2" style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
          Explorador
        </div>
        {ELEMENTOS_EXPLORADOR.map(renderizarBotonMenu)}

        <div className="text-uppercase small fw-semibold px-2 mb-2 mt-4" style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
          Gestión
        </div>
        {ELEMENTOS_GESTION.map(renderizarBotonMenu)}

        <div className="mt-auto pt-4">
          <div
            className="p-3"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}
          >
            <div className="d-flex justify-content-between small mb-2">
              <span className="fw-semibold">Almacenamiento</span>
              <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                {almacenamientoUsadoGb}/{almacenamientoTotalGb} GB
              </span>
            </div>
            <div
              className="mb-2"
              style={{ height: '6px', borderRadius: '3px', backgroundColor: 'rgba(255,255,255,0.15)' }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${porcentajeUsado}%`,
                  borderRadius: '3px',
                  backgroundColor: COLOR_MARCA,
                }}
              />
            </div>
            <p className="small mb-3" style={{ color: 'rgba(255,255,255,0.5)' }}>
              {almacenamientoTotalGb - almacenamientoUsadoGb} GB disponibles
            </p>
            <button
              type="button"
              className="btn btn-outline-light w-100 btn-sm fw-semibold"
              style={{ borderRadius: '8px' }}
            >
              Ampliar Plan
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido principal: se arma en el siguiente paso */}
      <main className="flex-grow-1 p-4" style={{ backgroundColor: '#F1F5F9' }}>
        <div className="d-flex justify-content-between align-items-center gap-3 mb-4">
          <h1 className="fs-4 mb-0">Hola, {usuario?.nombreCompleto}</h1>
          <button type="button" className="btn btn-outline-secondary d-flex align-items-center gap-2" onClick={manejarSalida}>
            <LogOut size={18} /> Cerrar sesión
          </button>
        </div>
        <p className="text-secondary">Sección activa: {seccionActiva}</p>
        {/* TODO: tabla de archivos, tarjetas de carpetas y panel de detalles */}
      </main>
    </div>
  )
}

export default DashboardPage
