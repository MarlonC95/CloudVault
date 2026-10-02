import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cloud, Upload, HardDrive, Users, Clock, Trash2, Zap, Shield } from 'lucide-react'
import { cerrarSesion, obtenerSesion } from '../services/authService'
import { COLOR_MARCA, COLOR_NAVY, COLOR_FONDO_PAGINA } from '../theme/colores'
import { CARPETAS_EJEMPLO, ARCHIVOS_EJEMPLO, CARGAS_EJEMPLO } from '../data/datosEjemplo'
import { cumpleRangoFecha, cumpleRangoTamano } from '../utils/filtrosArchivos'
import type { RangoFecha, RangoTamano } from '../utils/filtrosArchivos'
import type { Archivo, TipoArchivo } from '../types/archivo'
import BarraSuperior from '../components/dashboard/BarraSuperior'
import BuscadorArchivos from '../components/dashboard/BuscadorArchivos'
import TarjetaCarpeta from '../components/dashboard/TarjetaCarpeta'
import TablaArchivos from '../components/dashboard/TablaArchivos'
import PanelDetalleArchivo from '../components/dashboard/PanelDetalleArchivo'
import NotificacionCargas from '../components/dashboard/NotificacionCargas'
import ModalSubirArchivo from '../components/dashboard/ModalSubirArchivo'
import ModalCompartir from '../components/dashboard/ModalCompartir'

type SeccionExplorador = 'mi-unidad' | 'compartidos' | 'recientes' | 'papelera' | 'planes' | 'administracion'
type FiltroTipo = TipoArchivo | 'todos'

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
  const [archivos, setArchivos] = useState<Archivo[]>(ARCHIVOS_EJEMPLO)
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<FiltroTipo>('todos')
  const [filtroFecha, setFiltroFecha] = useState<RangoFecha>('cualquiera')
  const [filtroTamano, setFiltroTamano] = useState<RangoTamano>('cualquiera')
  const [archivoSeleccionado, setArchivoSeleccionado] = useState<Archivo | null>(null)
  const [archivoParaCompartir, setArchivoParaCompartir] = useState<Archivo | null>(null)
  const [mostrarModalSubida, setMostrarModalSubida] = useState(false)
  const [cargas] = useState(CARGAS_EJEMPLO)

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

  const archivosFiltrados = archivos
    .filter((archivo) => !archivo.enPapelera)
    .filter((archivo) => archivo.nombre.toLowerCase().includes(busqueda.toLowerCase()))
    .filter((archivo) => filtroTipo === 'todos' || archivo.tipo === filtroTipo)
    .filter((archivo) => cumpleRangoFecha(archivo.fechaModificacion, filtroFecha))
    .filter((archivo) => cumpleRangoTamano(archivo.tamano, filtroTamano))

  function manejarDescargar(archivo: Archivo) {
    // TODO(backend): reemplazar por la descarga real desde la URL prefirmada de S3/MinIO
    const contenido = `Archivo de ejemplo generado por CloudVault.\n\nNombre: ${archivo.nombre}\nTamaño reportado: ${archivo.tamano}`
    const blob = new Blob([contenido], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = archivo.nombre
    enlace.click()
    URL.revokeObjectURL(url)
  }

  function manejarEliminar(archivo: Archivo) {
    setArchivos((anteriores) =>
      anteriores.map((a) => (a.id === archivo.id ? { ...a, enPapelera: true } : a))
    )
    if (archivoSeleccionado?.id === archivo.id) {
      setArchivoSeleccionado(null)
    }
  }

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
        onClick={() => setSeccionActiva(elemento.id)}
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
          onClick={() => setMostrarModalSubida(true)}
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
            <div className="d-flex justify-content-between small mb-2">
              <span className="fw-semibold">Almacenamiento</span>
              <span style={{ color: 'rgba(255,255,255,0.6)' }}>
                {almacenamientoUsadoGb}/{almacenamientoTotalGb} GB
              </span>
            </div>
            <div className="mb-2" style={{ height: '6px', borderRadius: '3px', backgroundColor: 'rgba(255,255,255,0.15)' }}>
              <div style={{ height: '100%', width: `${porcentajeUsado}%`, borderRadius: '3px', backgroundColor: COLOR_MARCA }} />
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

      <div className="d-flex flex-column flex-grow-1" style={{ height: '100vh', overflow: 'hidden', minWidth: 0 }}>
        <BarraSuperior nombreUsuario={usuario?.nombreCompleto ?? 'Usuario'} onCerrarSesion={manejarSalida} />

        <main style={{ flex: 1, padding: 28, display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0, overflowY: 'auto', backgroundColor: COLOR_FONDO_PAGINA }}>
          <BuscadorArchivos
            valorBusqueda={busqueda}
            onCambiarBusqueda={setBusqueda}
            filtroTipo={filtroTipo}
            onCambiarFiltroTipo={setFiltroTipo}
            filtroFecha={filtroFecha}
            onCambiarFiltroFecha={setFiltroFecha}
            filtroTamano={filtroTamano}
            onCambiarFiltroTamano={setFiltroTamano}
          />

          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#64748B', letterSpacing: '0.07em', marginBottom: 12 }}>
                  CARPETAS PRINCIPALES
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                  {CARPETAS_EJEMPLO.map((carpeta) => (
                    <TarjetaCarpeta key={carpeta.id} carpeta={carpeta} />
                  ))}
                </div>
              </div>

              <TablaArchivos
                archivos={archivosFiltrados}
                archivoSeleccionadoId={archivoSeleccionado?.id ?? null}
                onSeleccionarArchivo={setArchivoSeleccionado}
                onDescargar={manejarDescargar}
                onCompartir={setArchivoParaCompartir}
                onEliminar={manejarEliminar}
              />
            </div>

            <PanelDetalleArchivo
              archivo={archivoSeleccionado}
              onDescargar={manejarDescargar}
              onCompartir={setArchivoParaCompartir}
              onEliminar={manejarEliminar}
            />
          </div>
        </main>
      </div>

      <NotificacionCargas cargas={cargas} />

      <ModalSubirArchivo
        visible={mostrarModalSubida}
        onCerrar={() => setMostrarModalSubida(false)}
        onConfirmarSubida={(archivos) => {
          console.log('Archivos a subir:', archivos)
          // TODO(backend): reemplazar por la llamada real de subida a la API
          setMostrarModalSubida(false)
        }}
      />

      <ModalCompartir archivo={archivoParaCompartir} onCerrar={() => setArchivoParaCompartir(null)} />
    </div>
  )
}

export default DashboardPage