import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { X, Link2, Check, UserPlus, Trash2 } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../../services/errorApi'
import {
  actualizarPermiso,
  compartirConUsuario,
  guardarEnlace,
  listarPermisos,
  obtenerEnlace,
  quitarPermiso,
  revocarEnlace,
} from '../../services/enlacesService'
import { NIVELES_ACCESO, nivelDe } from '../../types/enlaces'
import type { EnlaceCompartido, NivelAcceso, PermisoUsuario, RecursoCompartible } from '../../types/enlaces'

interface ModalCompartirProps {
  recurso: RecursoCompartible | null
  onCerrar: () => void
}

/** ISO del backend → 'YYYY-MM-DD' local para el `<input type="date">`. */
const aFechaLocal = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('en-CA') : '')

function ModalCompartir({ recurso, onCerrar }: ModalCompartirProps) {
  if (!recurso) return null
  // La key reinicia el estado al compartir otro recurso.
  return <PanelCompartir key={`${recurso.tipo}:${recurso.id}`} recurso={recurso} onCerrar={onCerrar} />
}

function PanelCompartir({ recurso, onCerrar }: { recurso: RecursoCompartible; onCerrar: () => void }) {
  const niveles = (Object.keys(NIVELES_ACCESO) as NivelAcceso[]).filter((n) => n !== 'subir' || recurso.tipo === 'carpeta')

  const [cargando, setCargando] = useState(true)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [permisos, setPermisos] = useState<PermisoUsuario[]>([])
  const [correo, setCorreo] = useState('')
  const [nivelPersona, setNivelPersona] = useState<NivelAcceso>('ver')

  const [enlace, setEnlace] = useState<EnlaceCompartido | null>(null)
  const [nivelEnlace, setNivelEnlace] = useState<NivelAcceso>('ver')
  const [fechaEnlace, setFechaEnlace] = useState('')
  const [password, setPassword] = useState('')
  const [quitarPassword, setQuitarPassword] = useState(false)
  const [copiado, setCopiado] = useState(false)

  function aplicarEnlace(e: EnlaceCompartido | null) {
    setEnlace(e)
    setPassword('')
    setQuitarPassword(false)
    if (e) {
      setNivelEnlace(nivelDe(e.rol, e.permiteDescarga))
      setFechaEnlace(aFechaLocal(e.fechaExpiracion))
    }
  }

  useEffect(() => {
    Promise.all([listarPermisos(recurso), obtenerEnlace(recurso)])
      .then(([p, e]) => {
        setPermisos(p)
        aplicarEnlace(e)
      })
      .catch((causa) => setError(convertirEnErrorApi(causa).message))
      .finally(() => setCargando(false))
  }, [recurso])

  /** Ejecuta una acción mostrando su error; `campo` elige el mensaje de validación preferido. */
  async function ejecutar(accion: () => Promise<void>, campo?: string) {
    setOcupado(true)
    setError(null)
    try {
      await accion()
    } catch (causa) {
      const errorApi = convertirEnErrorApi(causa)
      setError((campo && obtenerMensajeDeCampo(errorApi, campo)) || errorApi.message)
    } finally {
      setOcupado(false)
    }
  }

  function compartir(evento: FormEvent) {
    evento.preventDefault()
    if (!correo.trim()) return
    const { rol, permiteDescarga } = NIVELES_ACCESO[nivelPersona]
    void ejecutar(async () => {
      const nuevo = await compartirConUsuario(recurso, correo.trim(), rol, permiteDescarga)
      setPermisos((lista) => [...lista.filter((p) => p.id !== nuevo.id), nuevo])
      setCorreo('')
    }, 'correo')
  }

  function cambiarNivel(permiso: PermisoUsuario, nivel: NivelAcceso) {
    const { rol, permiteDescarga } = NIVELES_ACCESO[nivel]
    void ejecutar(async () => {
      const actualizado = await actualizarPermiso(permiso.id, rol, permiteDescarga)
      setPermisos((lista) => lista.map((p) => (p.id === actualizado.id ? actualizado : p)))
    })
  }

  function quitar(permiso: PermisoUsuario) {
    void ejecutar(async () => {
      await quitarPermiso(permiso.id)
      setPermisos((lista) => lista.filter((p) => p.id !== permiso.id))
    })
  }

  function guardar(evento: FormEvent) {
    evento.preventDefault()
    const { rol, permiteDescarga } = NIVELES_ACCESO[nivelEnlace]
    void ejecutar(async () => {
      aplicarEnlace(
        await guardarEnlace(recurso, {
          rol,
          permiteDescarga,
          // Caduca al final del día elegido, en la zona horaria del usuario.
          fechaExpiracion: fechaEnlace ? new Date(`${fechaEnlace}T23:59:59`).toISOString() : null,
          password: quitarPassword ? null : password || undefined,
        }),
      )
    }, 'fecha_expiracion')
  }

  function revocar() {
    if (!enlace) return
    void ejecutar(async () => {
      await revocarEnlace(enlace.id)
      setEnlace(null)
    })
  }

  const url = enlace ? `${window.location.origin}/s/${enlace.token}` : ''

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      setError('No se pudo copiar; selecciona el enlace y cópialo a mano.')
    }
  }

  const selectorNivel = (valor: NivelAcceso, alCambiar: (n: NivelAcceso) => void, etiqueta: string) => (
    <select
      className="form-select form-select-sm"
      style={{ width: 'auto' }}
      value={valor}
      aria-label={etiqueta}
      disabled={ocupado}
      onChange={(e) => alCambiar(e.target.value as NivelAcceso)}
    >
      {niveles.map((n) => (
        <option key={n} value={n}>
          {NIVELES_ACCESO[n].etiqueta}
        </option>
      ))}
    </select>
  )

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={onCerrar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-compartir"
        className="bg-white w-100"
        style={{ maxWidth: '520px', maxHeight: '90vh', overflowY: 'auto', borderRadius: '20px', padding: '24px', margin: '0 16px' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 id="titulo-compartir" className="fw-bold mb-0 text-truncate">
            Compartir «{recurso.nombre}»
          </h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>

        {error && <p role="alert" className="small text-danger">{error}</p>}

        {cargando ? (
          <p className="text-secondary small">Cargando…</p>
        ) : (
          <>
            <h6 className="fw-semibold small text-uppercase text-secondary">Personas con acceso</h6>
            <form className="d-flex gap-2 mb-3" onSubmit={compartir}>
              <input
                type="email"
                required
                className="form-control form-control-sm"
                placeholder="Correo de un usuario de CloudVault"
                aria-label="Correo"
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
              />
              {selectorNivel(nivelPersona, setNivelPersona, 'Nivel de acceso para el nuevo usuario')}
              <button
                type="submit"
                className="btn btn-sm text-white d-flex align-items-center gap-1"
                style={{ backgroundColor: COLOR_MARCA }}
                disabled={ocupado}
              >
                <UserPlus size={16} /> Compartir
              </button>
            </form>

            {permisos.length === 0 ? (
              <p className="small text-secondary">Todavía no lo compartiste con nadie.</p>
            ) : (
              <ul className="list-unstyled mb-3">
                {permisos.map((p) => (
                  <li key={p.id} className="d-flex align-items-center gap-2 py-1">
                    <div className="flex-grow-1" style={{ minWidth: 0 }}>
                      <div className="small fw-semibold text-truncate">{p.nombre || p.correo}</div>
                      <div className="small text-secondary text-truncate">
                        {p.correo}
                        {p.viaEnlace && ' · se unió por enlace'}
                      </div>
                    </div>
                    {selectorNivel(nivelDe(p.rol, p.permiteDescarga), (n) => cambiarNivel(p, n), `Nivel de acceso de ${p.correo}`)}
                    <button
                      type="button"
                      className="btn btn-sm p-1 text-danger"
                      aria-label={`Quitar acceso a ${p.correo}`}
                      disabled={ocupado}
                      onClick={() => quitar(p)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <hr />

            <h6 className="fw-semibold small text-uppercase text-secondary">Enlace</h6>
            {enlace && (
              <div className="d-flex align-items-center gap-2 mb-2">
                <div
                  className="d-flex align-items-center gap-2 flex-grow-1"
                  style={{ border: '1px solid #E2E8F0', borderRadius: '10px', padding: '6px 12px', minWidth: 0 }}
                >
                  <Link2 size={16} className="text-secondary flex-shrink-0" />
                  <input readOnly className="form-control-plaintext form-control-sm p-0 small" value={url} aria-label="Enlace" onFocus={(e) => e.target.select()} />
                </div>
                <button
                  type="button"
                  className="btn btn-sm text-white d-flex align-items-center gap-1"
                  style={{ backgroundColor: copiado ? '#16A34A' : COLOR_MARCA }}
                  onClick={copiar}
                >
                  {copiado ? <Check size={16} /> : <Link2 size={16} />} {copiado ? 'Copiado' : 'Copiar'}
                </button>
              </div>
            )}

            <form onSubmit={guardar}>
              <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
                <span className="small">Quien tenga el enlace:</span>
                {selectorNivel(nivelEnlace, setNivelEnlace, 'Nivel de acceso del enlace')}
              </div>
              {nivelEnlace === 'subir' && (
                <p className="small text-secondary mb-2">Para subir archivos, la persona deberá iniciar sesión.</p>
              )}
              <div className="row g-2 mb-2">
                <label className="col-sm-6 small">
                  Caduca el (opcional)
                  <input
                    type="date"
                    className="form-control form-control-sm"
                    min={new Date().toLocaleDateString('en-CA')}
                    value={fechaEnlace}
                    onChange={(e) => setFechaEnlace(e.target.value)}
                  />
                </label>
                <label className="col-sm-6 small">
                  Contraseña (opcional)
                  <input
                    type="password"
                    autoComplete="new-password"
                    maxLength={128}
                    className="form-control form-control-sm"
                    placeholder={enlace?.requierePassword ? 'Se conserva la actual' : 'Sin contraseña'}
                    disabled={quitarPassword}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
              </div>
              {enlace?.requierePassword && (
                <label className="form-check small mb-2">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    checked={quitarPassword}
                    onChange={(e) => setQuitarPassword(e.target.checked)}
                  />
                  Quitar la contraseña
                </label>
              )}
              <div className="d-flex gap-2 justify-content-end">
                {enlace && (
                  <button type="button" className="btn btn-sm btn-outline-danger" disabled={ocupado} onClick={revocar}>
                    Desactivar enlace
                  </button>
                )}
                <button type="submit" className="btn btn-sm text-white" style={{ backgroundColor: COLOR_MARCA }} disabled={ocupado}>
                  {enlace ? 'Guardar cambios' : 'Crear enlace'}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}

export default ModalCompartir
