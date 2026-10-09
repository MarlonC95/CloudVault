import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronLeft, Folder as FolderIcon } from 'lucide-react'
import { CARGAS_EJEMPLO } from '../data/datosEjemplo'
import { useArchivos } from '../context/archivosContexto'
import { cumpleRangoFecha, cumpleRangoTamano } from '../utils/filtrosArchivos'
import { obtenerTipoArchivoPorNombre, formatearTamanoBytes } from '../utils/formatoArchivo'
import { obtenerSesion } from '../services/authService'
import type { RangoFecha, RangoTamano } from '../utils/filtrosArchivos'
import type { Archivo, TipoArchivo } from '../types/archivo'
import DashboardLayout from '../components/layout/DashboardLayout'
import BuscadorArchivos from '../components/dashboard/BuscadorArchivos'
import TarjetaCarpeta from '../components/dashboard/TarjetaCarpeta'
import TarjetaNuevaCarpeta from '../components/dashboard/TarjetaNuevaCarpeta'
import ModalNuevaCarpeta from '../components/dashboard/ModalNuevaCarpeta'
import TablaArchivos from '../components/dashboard/TablaArchivos'
import PanelDetalleArchivo from '../components/dashboard/PanelDetalleArchivo'
import NotificacionCargas from '../components/dashboard/NotificacionCargas'
import ModalSubirArchivo from '../components/dashboard/ModalSubirArchivo'
import ModalCompartir from '../components/dashboard/ModalCompartir'
import ModalMoverArchivo from '../components/dashboard/ModalMoverArchivo'

type FiltroTipo = TipoArchivo | 'todos'

interface EstadoNavegacionDashboard {
  abrirSubida?: boolean
}

function DashboardPage() {
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const { carpetas, archivos, agregarArchivos, crearCarpeta, moverArchivo, enviarAPapelera } = useArchivos()

  // El botón "Subir Archivo" del menú, desde otras pantallas, nos trae aquí con la ventana de subida pedida.
  const debeAbrirSubida = (ubicacion.state as EstadoNavegacionDashboard | null)?.abrirSubida === true

  const [carpetaActivaId, setCarpetaActivaId] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<FiltroTipo>('todos')
  const [filtroFecha, setFiltroFecha] = useState<RangoFecha>('cualquiera')
  const [filtroTamano, setFiltroTamano] = useState<RangoTamano>('cualquiera')
  const [archivoSeleccionado, setArchivoSeleccionado] = useState<Archivo | null>(null)
  const [archivoParaCompartir, setArchivoParaCompartir] = useState<Archivo | null>(null)
  const [archivoParaMover, setArchivoParaMover] = useState<Archivo | null>(null)
  const [mostrarModalSubida, setMostrarModalSubida] = useState(debeAbrirSubida)
  const [mostrarModalNuevaCarpeta, setMostrarModalNuevaCarpeta] = useState(false)
  const [cargas] = useState(CARGAS_EJEMPLO)

  const usuario = obtenerSesion()?.usuario

  useEffect(() => {
    // Limpiamos el aviso para que la ventana no se reabra al recargar o volver atrás
    if (debeAbrirSubida) {
      navegar(ubicacion.pathname, { replace: true, state: null })
    }
  }, [debeAbrirSubida, navegar, ubicacion.pathname])

  function contarArchivosDeCarpeta(carpetaId: string) {
    return archivos.filter((archivo) => archivo.carpetaId === carpetaId && !archivo.enPapelera).length
  }

  const carpetaActiva = carpetas.find((carpeta) => carpeta.id === carpetaActivaId) ?? null

  const archivosFiltrados = archivos
    .filter((archivo) => !archivo.enPapelera)
    .filter((archivo) => carpetaActivaId === null || archivo.carpetaId === carpetaActivaId)
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
    enviarAPapelera(archivo.id)
    if (archivoSeleccionado?.id === archivo.id) {
      setArchivoSeleccionado(null)
    }
  }

  function manejarMover(archivo: Archivo, nuevaCarpetaId: string | null) {
    moverArchivo(archivo.id, nuevaCarpetaId)
    setArchivoParaMover(null)
  }

  function manejarCrearCarpeta(nombre: string) {
    crearCarpeta(nombre)
    setMostrarModalNuevaCarpeta(false)
  }

  function manejarConfirmarSubida(archivosSubidos: File[]) {
    // TODO(backend): reemplazar por la subida real a la API (POST /api/archivos/ con URL prefirmada de S3/MinIO)
    const nuevosArchivos: Archivo[] = archivosSubidos.map((archivo, indice) => ({
      id: `subido-${Date.now()}-${indice}`,
      nombre: archivo.name,
      tipo: obtenerTipoArchivoPorNombre(archivo.name),
      fechaModificacion: 'Justo ahora',
      tamano: formatearTamanoBytes(archivo.size),
      propietario: usuario?.nombreCompleto ?? 'Usuario',
      cifrado: false,
      esNuevo: true,
      carpetaId: carpetaActivaId,
      enPapelera: false,
    }))

    agregarArchivos(nuevosArchivos)
    setMostrarModalSubida(false)
  }

  return (
    <DashboardLayout seccionActiva="mi-unidad" onClickSubirArchivo={() => setMostrarModalSubida(true)}>
      <div style={{ flex: 1, padding: 28, display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
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
            {carpetaActiva ? (
              <button
                type="button"
                onClick={() => setCarpetaActivaId(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#2563EB',
                }}
              >
                <ChevronLeft size={16} />
                Mi Unidad
                <span style={{ color: '#CBD5E1' }}>/</span>
                <FolderIcon size={14} color={carpetaActiva.color} />
                {carpetaActiva.nombre}
              </button>
            ) : (
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#64748B', letterSpacing: '0.07em', marginBottom: 12 }}>
                  CARPETAS PRINCIPALES
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                  {carpetas.map((carpeta) => (
                    <TarjetaCarpeta
                      key={carpeta.id}
                      carpeta={carpeta}
                      cantidadArchivos={contarArchivosDeCarpeta(carpeta.id)}
                      estaActiva={carpeta.id === carpetaActivaId}
                      onClick={() => setCarpetaActivaId(carpeta.id)}
                    />
                  ))}
                  <TarjetaNuevaCarpeta onClick={() => setMostrarModalNuevaCarpeta(true)} />
                </div>
              </div>
            )}

            <TablaArchivos
              archivos={archivosFiltrados}
              archivoSeleccionadoId={archivoSeleccionado?.id ?? null}
              onSeleccionarArchivo={setArchivoSeleccionado}
              onDescargar={manejarDescargar}
              onCompartir={setArchivoParaCompartir}
              onEliminar={manejarEliminar}
              onMover={setArchivoParaMover}
              titulo={carpetaActiva ? carpetaActiva.nombre.toUpperCase() : 'TODOS LOS ARCHIVOS'}
            />
          </div>

          <PanelDetalleArchivo
            archivo={archivoSeleccionado}
            onDescargar={manejarDescargar}
            onCompartir={setArchivoParaCompartir}
            onEliminar={manejarEliminar}
            onMover={setArchivoParaMover}
          />
        </div>
      </div>

      <NotificacionCargas cargas={cargas} />

      <ModalSubirArchivo
        visible={mostrarModalSubida}
        onCerrar={() => setMostrarModalSubida(false)}
        onConfirmarSubida={manejarConfirmarSubida}
      />

      <ModalCompartir archivo={archivoParaCompartir} onCerrar={() => setArchivoParaCompartir(null)} />

      <ModalMoverArchivo
        archivo={archivoParaMover}
        carpetas={carpetas}
        onCerrar={() => setArchivoParaMover(null)}
        onMover={manejarMover}
      />

      <ModalNuevaCarpeta
        visible={mostrarModalNuevaCarpeta}
        onCerrar={() => setMostrarModalNuevaCarpeta(false)}
        onCrear={manejarCrearCarpeta}
      />
    </DashboardLayout>
  )
}

export default DashboardPage