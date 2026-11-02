import { useEffect, useState } from 'react'
import { ChevronLeft } from 'lucide-react'
import { COLOR_NAVY } from '../theme/colores'
import { convertirEnErrorApi } from '../services/errorApi'
import { obtenerUrlDescarga, obtenerUrlVistaPrevia } from '../services/archivosService'
import { listarCompartidosConmigo, obtenerContenidoCompartido } from '../services/enlacesService'
import type { ContenidoCarpeta, ElementoCompartido } from '../types/enlaces'
import DashboardLayout from '../components/layout/DashboardLayout'
import ListaContenido from '../components/compartir/ListaContenido'
import SubirAqui from '../components/compartir/SubirAqui'

type Vista =
  | { tipo: 'raiz'; elementos: ElementoCompartido[] }
  | { tipo: 'carpeta'; contenido: ContenidoCarpeta & { puedeSubir: boolean } }

const obtenerUrl = (archivoId: string, accion: 'ver' | 'descargar') =>
  accion === 'ver' ? obtenerUrlVistaPrevia(archivoId) : obtenerUrlDescarga(archivoId)

function CompartidosPage() {
  const [carpetaId, setCarpetaId] = useState<string | null>(null)
  const [recarga, setRecarga] = useState(0)
  const [vista, setVista] = useState<Vista | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    const peticion: Promise<Vista> = carpetaId
      ? obtenerContenidoCompartido(carpetaId).then((contenido) => ({ tipo: 'carpeta', contenido }))
      : listarCompartidosConmigo().then((elementos) => ({ tipo: 'raiz', elementos }))
    peticion
      .then((nueva) => {
        if (!cancelado) setVista(nueva)
      })
      .catch((causa) => {
        if (!cancelado) setError(convertirEnErrorApi(causa).message)
      })
    return () => {
      cancelado = true
    }
  }, [carpetaId, recarga])

  function irA(id: string | null) {
    setVista(null)
    setError(null)
    setCarpetaId(id)
  }

  function recargar() {
    setError(null)
    setRecarga((n) => n + 1)
  }

  const carpeta = vista?.tipo === 'carpeta' ? vista.contenido : null

  return (
    <DashboardLayout seccionActiva="compartidos">
      <div style={{ padding: 32 }}>
        <div className="d-flex align-items-center gap-2 mb-3 flex-wrap">
          {carpetaId && (
            <button
              type="button"
              className="btn btn-sm p-1"
              aria-label="Volver"
              onClick={() => irA(carpeta?.carpeta.padreId ?? null)}
            >
              <ChevronLeft size={20} />
            </button>
          )}
          <h1 className="mb-0 text-truncate" style={{ fontSize: 24, fontWeight: 700, color: COLOR_NAVY }}>
            {carpeta ? carpeta.carpeta.nombre : 'Compartidos conmigo'}
          </h1>
          {carpeta?.puedeSubir && (
            <div className="ms-auto d-flex align-items-center gap-2">
              <SubirAqui carpetaId={carpeta.carpeta.id} onSubido={recargar} />
            </div>
          )}
        </div>

        {error && (
          <p role="alert" className="small text-danger">
            {error}{' '}
            <button type="button" className="btn btn-link btn-sm p-0" onClick={recargar}>
              Reintentar
            </button>
          </p>
        )}
        {!vista && !error && <p role="status" className="small text-secondary">Cargando…</p>}

        {vista?.tipo === 'raiz' &&
          (vista.elementos.length === 0 ? (
            <p className="text-secondary small">Nadie ha compartido nada contigo todavía.</p>
          ) : (
            <ListaContenido
              carpetas={vista.elementos.filter((e) => e.tipo === 'carpeta')}
              archivos={vista.elementos.filter((e) => e.tipo === 'archivo')}
              onAbrirCarpeta={(c) => irA(c.id)}
              obtenerUrl={obtenerUrl}
            />
          ))}

        {carpeta && (
          <ListaContenido
            carpetas={carpeta.carpetas}
            archivos={carpeta.archivos.map((a) => ({ ...a, permiteDescarga: carpeta.permiteDescarga }))}
            onAbrirCarpeta={(c) => irA(c.id)}
            obtenerUrl={obtenerUrl}
          />
        )}
      </div>
    </DashboardLayout>
  )
}

export default CompartidosPage
