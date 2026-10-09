import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cloud, Upload, HardDrive, Users, Clock, Trash2, Zap, Shield } from 'lucide-react'
import { cerrarSesionEnServidor, obtenerSesion } from '../../services/authService'
import { obtenerResumenAlmacenamiento } from '../../services/unidadService'
import { ErrorApi } from '../../services/errorApi'
import { COLOR_MARCA, COLOR_NAVY, COLOR_FONDO_PAGINA } from '../../theme/colores'
import BarraSuperior from '../dashboard/BarraSuperior'
import type { ResumenAlmacenamiento } from '../../types/unidad'

export type SeccionExplorador =
  | 'mi-unidad'
  | 'compartidos'
  | 'recientes'
  | 'papelera'
  | 'planes'
  | 'administracion'

interface ElementoMenu {
  id: SeccionExplorador
  etiqueta: string
  icono: ReactNode
  ruta: string
}

const ELEMENTOS_EXPLORADOR: ElementoMenu[] = [
  { id: 'mi-unidad', etiqueta: 'Mi Unidad', icono: <HardDrive size={18} />, ruta: '/dashboard' },
  { id: 'compartidos', etiqueta: 'Compartidos conmigo', icono: <Users size={18} />, ruta: '/dashboard' },
  { id: 'recientes', etiqueta: 'Recientes', icono: <Clock size={18} />, ruta: '/dashboard' },
]

const ELEMENTOS_GESTION: ElementoMenu[] = [
  { id: 'papelera', etiqueta: 'Papelera', icono: <Trash2 size={18} />, ruta: '/papelera' },
  { id: 'planes', etiqueta: 'Planes', icono: <Zap size={18} />, ruta: '/planes' },
  { id: 'administracion', etiqueta: 'Administración', icono: <Shield size={18} />, ruta: '/administracion' },
]

interface DashboardLayoutProps {
  seccionActiva?: SeccionExplorador
  onClickSubirArchivo?: () => void
  children: ReactNode
}

function DashboardLayout({ seccionActiva, onClickSubirArchivo, children }: DashboardLayoutProps) {
  const navegar = useNavigate()
  const usuario = obtenerSesion()?.usuario

  const [resumen, setResumen] = useState<ResumenAlmacenamiento | null>(null)
  const [cargandoResumen, setCargandoResumen] = useState(true)
  const [errorResumen, setErrorResumen] = useState('')

  useEffect(() => {
    let cancelado = false
    obtenerResumenAlmacenamiento()
      .then((datos) => {
        if (!cancelado) setResumen(datos)
      })
      .catch((error) => {
        if (!cancelado) setErrorResumen(error instanceof ErrorApi ? error.message : 'No se pudo cargar el resumen.')
      })
      .finally(() => {
        if (!cancelado) setCargandoResumen(false)
      })
    return () => {
      cancelado = true
    }
  }, [])

  function manejarSalida() {
    void cerrarSesionEnServidor()
    navegar('/login', { replace: true })
  }

  const usadoTexto = resumen?.usadoLegible ?? '—'
  const totalTexto = resumen?.cuotaLegible ?? '—'
  const porcentajeUsado = resumen?.porcentajeUsado ?? 0

  function renderizarBotonMenu(elemento: ElementoMenu) {
    const estaActivo = seccionActiva === elemento.id
    return (
      <button
        key={elemento.id}
        type="button"
        className="btn d-flex align-items-center gap-2 w-100 text-start mb-1"
        style={{
          backgroundColor: estaActivo ? 'rgba(37,99,235,0.18)' : 'transparent',
          color: estaActivo ? '#FFFFFF' : 'rgba(255,255,255,0.7)',
          border: 'none',
          borderLeft: estaActivo ? `3px solid ${COLOR_MARCA}` : '3px solid transparent',
          borderRadius: '0 10px 10px 0',
          padding: '10px 11px',
        }}
        onClick={() => navegar(elemento.ruta)}
      >
        {elemento.icono}
        <span className="small fw-medium">{elemento.etiqueta}</span>
      </button>
    )
  }

  return (
    <div className="d-flex" style={{ height: '100vh', overflow: 'hidden' }}>
      <aside
        className="d-none d-lg-flex flex-column p-3 text-white flex-shrink-0"
        style={{ width: '260px', height: '100vh', backgroundColor: COLOR_NAVY, overflowY: 'auto' }}
      >
        <div className="d-flex align-items-center gap-2 mb-4 px-2">
          <Cloud size={26} color={COLOR_MARCA} />
          <span className="fw-bold fs-5">CloudVault PaaS</span>
        </div>

        <button
          type="button"
          className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold mb-4"
          style={{ backgroundColor: COLOR_MARCA, borderRadius: '10px', padding: '10px' }}
          onClick={() => {
            if (onClickSubirArchivo) {
              onClickSubirArchivo()
              return
            }
            // Desde otras pantallas (Papelera, Planes, Perfil…) llevamos al usuario a Mi Unidad con la subida abierta
            navegar('/dashboard', { state: { abrirSubida: true } })
          }}
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
          <div className="p-3" style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}>
            {cargandoResumen ? (
              <p className="small text-center mb-0" style={{ color: 'rgba(255,255,255,0.6)' }}>
                Cargando almacenamiento…
              </p>
            ) : errorResumen ? (
              <>
                <p className="small text-center mb-2" style={{ color: 'rgba(255,255,255,0.6)' }}>
                  {errorResumen}
                </p>
                <button
                  type="button"
                  className="btn btn-outline-light w-100 btn-sm fw-semibold"
                  style={{ borderRadius: '8px' }}
                  onClick={() => navegar('/planes')}
                >
                  Ampliar Plan
                </button>
              </>
            ) : (
              <>
                <div className="d-flex justify-content-between small mb-2">
                  <span className="fw-semibold">Almacenamiento</span>
                  <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                    {usadoTexto} / {totalTexto}
                  </span>
                </div>
                <div className="mb-2" style={{ height: '6px', borderRadius: '3px', backgroundColor: 'rgba(255,255,255,0.15)' }}>
                  <div
                    style={{ height: '100%', width: `${porcentajeUsado}%`, borderRadius: '3px', backgroundColor: COLOR_MARCA }}
                  />
                </div>
                <p className="small mb-3" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  {resumen?.libreLegible ?? '—'} disponibles
                </p>
                <button
                  type="button"
                  className="btn btn-outline-light w-100 btn-sm fw-semibold"
                  style={{ borderRadius: '8px' }}
                  onClick={() => navegar('/planes')}
                >
                  Ampliar Plan
                </button>
              </>
            )}
          </div>
        </div>
      </aside>

      <div className="d-flex flex-column flex-grow-1" style={{ height: '100vh', overflow: 'hidden', minWidth: 0 }}>
        <BarraSuperior nombreUsuario={usuario?.nombreCompleto ?? 'Usuario'} onCerrarSesion={manejarSalida} />

        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflowY: 'auto', backgroundColor: COLOR_FONDO_PAGINA }}>
          {children}
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout