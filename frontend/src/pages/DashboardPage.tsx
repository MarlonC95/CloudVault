import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ChevronLeft, Folder as FolderIcon } from 'lucide-react'
import { useArchivos } from '../context/archivosContexto'
import { subirArchivo, obtenerUrlDescarga } from '../services/archivosService'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../services/errorApi'
import { formatearTamanoBytes } from '../utils/formatoArchivo'
import type { RangoFecha, RangoTamano } from '../utils/filtrosArchivos'
import type { Archivo, CargaEnProgreso, TipoArchivo } from '../types/archivo'
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
  const { carpetas, archivos, cargando, error, refrescar, crearCarpeta, moverArchivo, enviarAPapelera } = useArchivos()

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
  const [cargas, setCargas] = useState<CargaEnProgreso[]>([])
  const [errorAccion, setErrorAccion] = useState<string | null>(null)
  const [ahora] = useState(() => Date.now())

  useEffect(() => {
    // Limpiamos el aviso para que la ventana no se reabra al recargar o volver atrás
    if (debeAbrirSubida) {
      navegar(ubicacion.pathname, { replace: true, state: null })
    }
  }, [debeAbrirSubida, navegar, ubicacion.pathname])

  const carpetaActiva = carpetas.find((carpeta) => carpeta.id === carpetaActivaId) ?? null

  const archivosFiltrados = archivos
    .filter((archivo) => !archivo.enPapelera)
    .filter((archivo) => carpetaActivaId === null || archivo.carpetaId === carpetaActivaId)
    .filter((archivo) => archivo.nombre.toLowerCase().includes(busqueda.toLowerCase()))
    .filter((archivo) => filtroTipo === 'todos' || archivo.tipo === filtroTipo)
    .filter((archivo) => {
      if (filtroFecha === 'cualquiera') return true
      const fecha = new Date(archivo.fechaModificacionIso).getTime()
      if (filtroFecha === 'recientes') return fecha >= ahora - 7 * 86400000
      if (filtroFecha === 'este-mes') return new Date(archivo.fechaModificacionIso).getMonth() === new Date(ahora).getMonth()
        && new Date(archivo.fechaModificacionIso).getFullYear() === new Date(ahora).getFullYear()
      return fecha < ahora - 30 * 86400000
    })
    .filter((archivo) => {
      if (filtroTamano === 'cualquiera') return true
      const mb = archivo.tamanoBytes / (1024 * 1024)
      return filtroTamano === 'pequeno' ? mb < 1 : filtroTamano === 'mediano' ? mb >= 1 && mb < 100 : mb >= 100
    })

  async function manejarDescargar(archivo: Archivo) {
    try {
      setErrorAccion(null)
      const descarga = await obtenerUrlDescarga(archivo.id)
      if (!descarga.url) throw new Error('La API no devolvió una URL de descarga.')
      const enlace = document.createElement('a')
      enlace.href = descarga.url
      enlace.download = descarga.nombre ?? archivo.nombre
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
    } catch (causa) { setErrorAccion(causa instanceof Error && causa.message.startsWith('La API') ? causa.message : convertirEnErrorApi(causa).message) }
  }

  async function manejarEliminar(archivo: Archivo) {
    try {
      await enviarAPapelera(archivo.id)
      if (archivoSeleccionado?.id === archivo.id) setArchivoSeleccionado(null)
    } catch (causa) { setErrorAccion(convertirEnErrorApi(causa).message) }
  }

  async function manejarMover(archivo: Archivo, nuevaCarpetaId: string | null) {
    try {
      await moverArchivo(archivo.id, nuevaCarpetaId)
      setArchivoParaMover(null)
    } catch (causa) { setErrorAccion(convertirEnErrorApi(causa).message); throw causa }
  }

  async function manejarCrearCarpeta(nombre: string) {
    try {
      await crearCarpeta(nombre)
      setMostrarModalNuevaCarpeta(false)
    } catch (causa) {
      const errorApi = convertirEnErrorApi(causa)
      setErrorAccion(obtenerMensajeDeCampo(errorApi, 'nombre') ?? errorApi.message)
      throw causa
    }
  }

  function manejarConfirmarSubida(archivosSubidos: File[]) {
    const entradas = archivosSubidos.map((archivo) => ({ archivo, id: crypto.randomUUID() }))
    setCargas((anteriores) => [...anteriores, ...entradas.map(({ archivo, id }) => ({ id, nombreArchivo: archivo.name, tamano: formatearTamanoBytes(archivo.size), progreso: 0, estado: 'en-cola' as const }))])
    setMostrarModalSubida(false)
    void (async () => {
      for (const { archivo, id } of entradas) {
        setCargas((anteriores) => anteriores.map((carga) => carga.id === id ? { ...carga, estado: 'subiendo' } : carga))
        try {
          await subirArchivo(archivo, carpetaActivaId, (progreso) => setCargas((anteriores) => anteriores.map((carga) => carga.id === id ? { ...carga, progreso } : carga)))
          setCargas((anteriores) => anteriores.map((carga) => carga.id === id ? { ...carga, progreso: 100, estado: 'completado' } : carga))
          await refrescar()
        } catch (causa) {
          const mensajeError = convertirEnErrorApi(causa).message
          setCargas((anteriores) => anteriores.map((carga) => carga.id === id ? { ...carga, estado: 'error', mensajeError } : carga))
        }
      }
    })()
  }

  return (
    <DashboardLayout seccionActiva="mi-unidad" onClickSubirArchivo={() => setMostrarModalSubida(true)}>
      <div style={{ flex: 1, padding: 28, display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
        {cargando && <div role="status" style={{ color: '#64748B', fontSize: 13 }}>Cargando archivos y carpetas...</div>}
        {(error || errorAccion) && <div role="alert" style={{ color: '#DC2626', fontSize: 13 }}>{errorAccion || error} <button type="button" onClick={() => { setErrorAccion(null); void refrescar().catch(() => undefined) }}>Reintentar</button></div>}
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
                      cantidadArchivos={carpeta.cantidadArchivos}
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

      <NotificacionCargas cargas={cargas} onDescartar={(id) => setCargas((anteriores) => anteriores.filter((carga) => carga.id !== id))} />

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
