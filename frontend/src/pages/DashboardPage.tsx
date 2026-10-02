import { useState } from 'react'
import { ChevronLeft, Folder as FolderIcon } from 'lucide-react'
import { CARPETAS_EJEMPLO, ARCHIVOS_EJEMPLO, CARGAS_EJEMPLO } from '../data/datosEjemplo'
import { cumpleRangoFecha, cumpleRangoTamano } from '../utils/filtrosArchivos'
import { obtenerTipoArchivoPorNombre, formatearTamanoBytes } from '../utils/formatoArchivo'
import { obtenerSesion } from '../services/authService'
import type { RangoFecha, RangoTamano } from '../utils/filtrosArchivos'
import type { Archivo, Carpeta, TipoArchivo } from '../types/archivo'
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

const COLORES_CARPETA_NUEVA = [
  { color: '#DB2777', colorFondo: '#FDF2F8' },
  { color: '#CA8A04', colorFondo: '#FEFCE8' },
  { color: '#059669', colorFondo: '#ECFDF5' },
]

function DashboardPage() {
  const [carpetas, setCarpetas] = useState<Carpeta[]>(CARPETAS_EJEMPLO)
  const [archivos, setArchivos] = useState<Archivo[]>(ARCHIVOS_EJEMPLO)
  const [carpetaActivaId, setCarpetaActivaId] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<FiltroTipo>('todos')
  const [filtroFecha, setFiltroFecha] = useState<RangoFecha>('cualquiera')
  const [filtroTamano, setFiltroTamano] = useState<RangoTamano>('cualquiera')
  const [archivoSeleccionado, setArchivoSeleccionado] = useState<Archivo | null>(null)
  const [archivoParaCompartir, setArchivoParaCompartir] = useState<Archivo | null>(null)
  const [archivoParaMover, setArchivoParaMover] = useState<Archivo | null>(null)
  const [mostrarModalSubida, setMostrarModalSubida] = useState(false)
  const [mostrarModalNuevaCarpeta, setMostrarModalNuevaCarpeta] = useState(false)
  const [cargas] = useState(CARGAS_EJEMPLO)

  const usuario = obtenerSesion()?.usuario

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
    setArchivos((anteriores) => anteriores.map((a) => (a.id === archivo.id ? { ...a, enPapelera: true } : a)))
    if (archivoSeleccionado?.id === archivo.id) {
      setArchivoSeleccionado(null)
    }
  }

  function manejarMover(archivo: Archivo, nuevaCarpetaId: string | null) {
    setArchivos((anteriores) =>
      anteriores.map((a) => (a.id === archivo.id ? { ...a, carpetaId: nuevaCarpetaId } : a))
    )
    setArchivoParaMover(null)
  }

  function manejarCrearCarpeta(nombre: string) {
    const paleta = COLORES_CARPETA_NUEVA[carpetas.length % COLORES_CARPETA_NUEVA.length]
    const nuevaCarpeta: Carpeta = {
      id: `carpeta-${Date.now()}`,
      nombre,
      color: paleta.color,
      colorFondo: paleta.colorFondo,
    }
    // TODO(backend): reemplazar por POST /api/carpetas/
    setCarpetas((anteriores) => [...anteriores, nuevaCarpeta])
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

    setArchivos((anteriores) => [...nuevosArchivos, ...anteriores])
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