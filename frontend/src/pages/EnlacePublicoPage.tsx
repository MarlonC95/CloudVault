import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, Cloud, Lock } from 'lucide-react'
import { COLOR_FONDO_PAGINA, COLOR_MARCA, COLOR_NAVY } from '../theme/colores'
import { obtenerSesion } from '../services/authService'
import { convertirEnErrorApi } from '../services/errorApi'
import {
  accederConPassword,
  obtenerArchivoPublico,
  obtenerContenidoPublico,
  obtenerPublico,
  olvidarAccesoPublico,
} from '../services/enlacesService'
import type { ContenidoCarpeta, RecursoPublico } from '../types/enlaces'
import ListaContenido from '../components/compartir/ListaContenido'
import SubirAqui from '../components/compartir/SubirAqui'

type Estado =
  | { fase: 'cargando' }
  | { fase: 'no-encontrado' }
  | { fase: 'error'; mensaje: string }
  | { fase: 'password' }
  | { fase: 'listo'; recurso: RecursoPublico; contenido: ContenidoCarpeta | null }

/** Página de un enlace compartido (/s/:token): funciona con o sin sesión. */
function EnlacePublicoPage() {
  const { token = '' } = useParams()
  const [carpetaId, setCarpetaId] = useState<string | undefined>(undefined)
  const [recarga, setRecarga] = useState(0)
  const [estado, setEstado] = useState<Estado>({ fase: 'cargando' })

  useEffect(() => {
    let cancelado = false
    async function cargar(): Promise<Estado> {
      const recurso = await obtenerPublico(token)
      if (recurso.bloqueado) return { fase: 'password' }
      const contenido = recurso.tipo === 'carpeta' ? await obtenerContenidoPublico(token, carpetaId) : null
      return { fase: 'listo', recurso, contenido }
    }
    cargar()
      .catch((causa): Estado => {
        const error = convertirEnErrorApi(causa)
        if (error.codigo === 'NO_ENCONTRADO') return { fase: 'no-encontrado' }
        if (error.codigo === 'SIN_PERMISO') {
          // El acceso con contraseña caducó (15 min) o la contraseña cambió: se vuelve a pedir.
          olvidarAccesoPublico(token)
          return { fase: 'password' }
        }
        return { fase: 'error', mensaje: error.message }
      })
      .then((nuevo) => {
        if (!cancelado) setEstado(nuevo)
      })
    return () => {
      cancelado = true
    }
  }, [token, carpetaId, recarga])

  function irA(id: string | undefined) {
    setEstado({ fase: 'cargando' })
    setCarpetaId(id)
  }

  const recargar = () => setRecarga((n) => n + 1)
  const sesion = obtenerSesion()

  return (
    <div style={{ minHeight: '100vh', background: COLOR_FONDO_PAGINA }}>
      <header className="bg-white border-bottom d-flex align-items-center gap-2 px-3 py-2">
        <Cloud size={22} color={COLOR_MARCA} />
        <span className="fw-bold" style={{ color: COLOR_NAVY }}>CloudVault</span>
        <Link to={sesion ? '/dashboard' : '/login'} className="ms-auto small">
          {sesion ? 'Ir a mi unidad' : 'Iniciar sesión'}
        </Link>
      </header>

      <main className="container py-4" style={{ maxWidth: 760 }}>
        {estado.fase === 'cargando' && <p role="status" className="text-secondary">Cargando…</p>}
        {estado.fase === 'no-encontrado' && (
          <p className="text-secondary">Este enlace no existe, se desactivó o ya caducó.</p>
        )}
        {estado.fase === 'error' && (
          <p role="alert" className="text-danger">
            {estado.mensaje}{' '}
            <button type="button" className="btn btn-link p-0 align-baseline" onClick={recargar}>
              Reintentar
            </button>
          </p>
        )}
        {estado.fase === 'password' && <FormularioPassword token={token} onAcceso={recargar} />}
        {estado.fase === 'listo' && (
          <Recurso
            token={token}
            recurso={estado.recurso}
            contenido={estado.contenido}
            conSesion={sesion !== null}
            onIrA={irA}
            onSubido={recargar}
          />
        )}
      </main>
    </div>
  )
}

function FormularioPassword({ token, onAcceso }: { token: string; onAcceso: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await accederConPassword(token, password)
      onAcceso()
    } catch (causa) {
      const errorApi = convertirEnErrorApi(causa)
      setError(errorApi.codigo === 'SIN_PERMISO' ? 'Contraseña incorrecta.' : errorApi.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="bg-white p-4 mx-auto" style={{ maxWidth: 380, borderRadius: 20 }} onSubmit={enviar}>
      <h1 className="h5 fw-bold d-flex align-items-center gap-2">
        <Lock size={18} /> Enlace protegido
      </h1>
      <label className="small w-100 mb-2">
        Contraseña
        <input
          type="password"
          required
          autoFocus
          autoComplete="off"
          className="form-control"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && <p role="alert" className="small text-danger">{error}</p>}
      <button type="submit" className="btn w-100 text-white" style={{ backgroundColor: COLOR_MARCA }} disabled={enviando}>
        Acceder
      </button>
    </form>
  )
}

interface RecursoProps {
  token: string
  recurso: RecursoPublico
  contenido: ContenidoCarpeta | null
  conSesion: boolean
  onIrA: (carpetaId: string | undefined) => void
  onSubido: () => void
}

function Recurso({ token, recurso, contenido, conSesion, onIrA, onSubido }: RecursoProps) {
  const permiteDescarga = recurso.permiteDescarga ?? false
  const obtenerUrl = (archivoId: string, accion: 'ver' | 'descargar') => obtenerArchivoPublico(token, archivoId, accion)
  const padreId = contenido?.carpeta.padreId

  return (
    <>
      <div className="d-flex align-items-center gap-2 mb-3 flex-wrap">
        {/* El backend devuelve padre_id null en la raíz del enlace: no se puede subir más arriba. */}
        {padreId && (
          <button type="button" className="btn btn-sm p-1" aria-label="Volver" onClick={() => onIrA(padreId)}>
            <ChevronLeft size={20} />
          </button>
        )}
        <h1 className="h4 fw-bold mb-0 text-truncate" style={{ color: COLOR_NAVY }}>
          {contenido ? contenido.carpeta.nombre : recurso.nombre}
        </h1>
        {recurso.puedeSubir && contenido && (
          <div className="ms-auto d-flex align-items-center gap-2">
            <SubirAqui carpetaId={contenido.carpeta.id} onSubido={onSubido} />
          </div>
        )}
      </div>

      {recurso.rol === 'ESCRITURA' && !conSesion && (
        <p className="small">
          <Link to={`/login?next=${encodeURIComponent(`/s/${token}`)}`}>Inicia sesión</Link> para subir archivos a esta
          carpeta.
        </p>
      )}
      {recurso.unido && (
        <p className="small text-secondary">
          También lo encontrarás en <Link to="/compartidos">Compartidos conmigo</Link>.
        </p>
      )}

      {contenido ? (
        <ListaContenido
          carpetas={contenido.carpetas}
          archivos={contenido.archivos.map((a) => ({ ...a, permiteDescarga }))}
          onAbrirCarpeta={(c) => onIrA(c.id)}
          obtenerUrl={obtenerUrl}
        />
      ) : (
        <ListaContenido
          carpetas={[]}
          archivos={[{ id: recurso.id ?? '', nombre: recurso.nombre ?? '', tamanoBytes: recurso.tamanoBytes ?? null, permiteDescarga }]}
          onAbrirCarpeta={() => undefined}
          obtenerUrl={obtenerUrl}
        />
      )}
    </>
  )
}

export default EnlacePublicoPage
