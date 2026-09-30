import { useState } from 'react'
import { Cloud, Upload, HardDrive, Users, Clock, Trash2, Zap, Shield } from 'lucide-react'
import { COLOR_MARCA, COLOR_NAVY, COLOR_FONDO_PAGINA } from '../theme/colores'
import { CARPETAS_EJEMPLO, ARCHIVOS_EJEMPLO, CARGAS_EJEMPLO } from '../data/datosEjemplo'
import type { Archivo } from '../types/archivo'
import BuscadorArchivos from '../components/dashboard/BuscadorArchivos'
import TarjetaCarpeta from '../components/dashboard/TarjetaCarpeta'
import TablaArchivos from '../components/dashboard/TablaArchivos'
import PanelDetalleArchivo from '../components/dashboard/PanelDetalleArchivo'
import NotificacionCargas from '../components/dashboard/NotificacionCargas'
import ModalSubirArchivo from '../components/dashboard/ModalSubirArchivo'

type SeccionExplorador = 'mi-unidad' | 'compartidos' | 'recientes' | 'papelera' | 'planes' | 'administracion'

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
  const [busqueda, setBusqueda] = useState('')
  const [archivoSeleccionado, setArchivoSeleccionado] = useState<Archivo | null>(null)
  const [mostrarModalSubida, setMostrarModalSubida] = useState(false)
  const [cargas, setCargas] = useState(CARGAS_EJEMPLO)

  // TODO: reemplazar por datos reales del plan del usuario cuando exista la API
  const almacenamientoUsadoGb = 45
  const almacenamientoTotalGb = 100
  const porcentajeUsado = (almacenamientoUsadoGb / almacenamientoTotalGb) * 100

  const archivosFiltrados = ARCHIVOS_EJEMPLO.filter((archivo) =>
    archivo.nombre.toLowerCase().includes(busqueda.toLowerCase())
  )

  function renderizarBotonMenu(elemento: ElementoMenu) {
    const estaActivo = seccionActiva === elemento.id
    return (
      <button
        key={elemento.id}
        type="button"
        className="btn d-flex align-items-center gap-2 w-100 text-start mb-1 border-0"
        style={{
          backgroundColor: estaActivo ? 'rgba(37,99,235,0.18)' : 'transparent',
          color: estaActivo ? '#FFFFFF' : 'rgba(255,255,255,0.7)',
          borderLeft: estaActivo ? `3px solid ${COLOR_MARCA}` : '3px solid transparent',
          borderRadius: '0 10px 10px 0',
          padding: '10px 11px',
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
          onClick={() => setMostrarModalSubida(true)}
        >
          <Upload size={18} />
          Subir Archivo
        </button>

        <div
          className="text-uppercase small fw-semibold px-2 mb-2"
          style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}
        >
          Explorador
        </div>
        {ELEMENTOS_EXPLORADOR.map(renderizarBotonMenu)}

        <div
          className="text-uppercase small fw-semibold px-2 mb-2 mt-4"
          style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}
        >
          Gestión
        </div>
        {ELEMENTOS_GESTION.map(renderizarBotonMenu)}

        <div className="mt-auto pt-4">
          <div className="p-3" style={{ backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}>
            <div className="d-flex justify-content-between small mb-2">
              <span className="fw-semibold">Almacenamiento</span>
              <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                {almacenamientoUsadoGb}/{almacenamientoTotalGb} GB
              </span>
            </div>
            <div className="mb-2" style={{ height: '6px', borderRadius: '3px', backgroundColor: 'rgba(255,255,255,0.15)' }}>
              <div
                style={{ height: '100%', width: `${porcentajeUsado}%`, borderRadius: '3px', backgroundColor: COLOR_MARCA }}
              />
            </div>
            <p className="small mb-3" style={{ color: 'rgba(255,255,255,0.5)' }}>
              {almacenamientoTotalGb - almacenamientoUsadoGb} GB disponibles
            </p>
            <button type="button" className="btn btn-outline-light w-100 btn-sm fw-semibold" style={{ borderRadius: '8px' }}>
              Ampliar Plan
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido principal */}
      <main className="flex-grow-1 p-4" style={{ backgroundColor: COLOR_FONDO_PAGINA }}>
        <BuscadorArchivos valorBusqueda={busqueda} onCambiarBusqueda={setBusqueda} />

        <p className="small fw-semibold text-secondary text-uppercase mb-2" style={{ letterSpacing: '0.04em' }}>
          Carpetas principales
        </p>
        <div className="row g-3 mb-4">
          {CARPETAS_EJEMPLO.map((carpeta) => (
            <div key={carpeta.id} className="col-12 col-md-4">
              <TarjetaCarpeta carpeta={carpeta} />
            </div>
          ))}
        </div>

        <div className="row g-3">
          <div className="col-12 col-xl-8">
            <TablaArchivos
              archivos={archivosFiltrados}
              archivoSeleccionadoId={archivoSeleccionado?.id ?? null}
              onSeleccionarArchivo={setArchivoSeleccionado}
            />
          </div>
          <div className="col-12 col-xl-4">
            <PanelDetalleArchivo archivo={archivoSeleccionado} />
          </div>
        </div>
      </main>

      <NotificacionCargas cargas={cargas} onCerrar={() => setCargas([])} />

      <ModalSubirArchivo
        visible={mostrarModalSubida}
        onCerrar={() => setMostrarModalSubida(false)}
        onConfirmarSubida={(archivos) => {
          console.log('Archivos a subir:', archivos)
          // TODO(backend): reemplazar por la llamada real de subida a la API
          setMostrarModalSubida(false)
        }}
      />
    </div>
  )
}

export default DashboardPage