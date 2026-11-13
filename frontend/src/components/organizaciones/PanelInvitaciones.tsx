import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Check, Clock, Inbox, Loader2, Mail, RefreshCw, Send, Trash2, UserPlus, X } from 'lucide-react'
import {
  decidirInvitacion,
  enviarInvitacion,
  listarInvitaciones,
  revocarInvitacion,
  type DecisionInvitacion,
} from '../../services/invitacionesService'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../../services/errorApi'
import type { RolMiembroEditable } from '../../services/organizacionesService'
import { COLOR_ICONO_FONDO, COLOR_MARCA, COLOR_NAVY } from '../../theme/colores'

const ETIQUETAS_ROL: Record<RolMiembroEditable, string> = {
  LECTOR_NV1: 'Lector',
  OPERATIVO_NV2: 'Operativo',
  AVANZADO_NV3: 'Avanzado',
}
const formatoFecha = new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium', timeStyle: 'short' })

const ESTILO_TARJETA = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E2E8F0',
  borderRadius: '18px',
  padding: '24px',
  boxShadow: '0 1px 4px rgba(15, 23, 42, 0.04)',
}

const ESTILO_INPUT = {
  backgroundColor: COLOR_ICONO_FONDO,
  border: '1px solid #DBEAFE',
  borderRadius: '10px',
  padding: '10px 14px',
  fontSize: '14px',
}

interface Props {
  organizacionId?: string
  ejecutar?: <T>(accion: () => Promise<T>) => Promise<T>
}

export default function PanelInvitaciones({ organizacionId, ejecutar }: Props) {
  const [consulta, setConsulta] = useState({ pagina: 1 })
  const [datos, setDatos] = useState<Awaited<ReturnType<typeof listarInvitaciones>> | null>(null)
  const [errorLista, setErrorLista] = useState('')
  const [errorAccion, setErrorAccion] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const operando = useRef(false)
  const [correo, setCorreo] = useState('')
  const [rol, setRol] = useState<RolMiembroEditable>('LECTOR_NV1')

  useEffect(() => {
    const controlador = new AbortController()
    void listarInvitaciones(consulta.pagina, controlador.signal, organizacionId)
      .then((lista) => {
        if (!controlador.signal.aborted) setDatos(lista)
      })
      .catch((causa) => {
        if (!controlador.signal.aborted) setErrorLista(convertirEnErrorApi(causa).message)
      })
    return () => controlador.abort()
  }, [consulta, organizacionId])

  function cargar(pagina: number) {
    setDatos(null)
    setErrorLista('')
    setConsulta({ pagina })
  }

  async function operar(accion: () => Promise<void>, confirmacion: string, despues?: () => void) {
    if (operando.current) return
    operando.current = true
    setOcupado(true)
    setMensaje('')
    setErrorAccion('')
    try {
      if (ejecutar) await ejecutar(accion)
      else await accion()
      setMensaje(confirmacion)
      despues?.()
      cargar(1)
    } catch (causa) {
      const error = convertirEnErrorApi(causa)
      setErrorAccion(obtenerMensajeDeCampo(error, 'correo_electronico') ?? error.message)
      if (error.estadoHttp === 403 || error.estadoHttp === 404 || error.codigo === 'INVITATION_CLOSED') cargar(1)
    } finally {
      operando.current = false
      setOcupado(false)
    }
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!organizacionId) return
    void operar(() => enviarInvitacion(organizacionId, correo.trim(), rol), 'Invitación enviada correctamente.', () => setCorreo(''))
  }

  function decidir(id: string, decision: DecisionInvitacion) {
    const acepta = decision === 'ACEPTAR'
    void operar(
      () => decidirInvitacion(id, decision),
      acepta ? 'Invitación aceptada. Ya puedes seleccionar el espacio en la barra superior.' : 'Invitación rechazada.',
    )
  }

  const cargandoLista = !datos && !errorLista

  return (
    <section aria-labelledby={organizacionId ? 'titulo-invitaciones-enviadas' : 'titulo-invitaciones-recibidas'}>
      {organizacionId && (
        <form onSubmit={enviar} style={{ ...ESTILO_TARJETA, marginBottom: '24px' }}>
          <div className="d-flex align-items-center gap-2 mb-2">
            <span
              className="d-inline-flex align-items-center justify-content-center"
              style={{ width: '34px', height: '34px', borderRadius: '9px', backgroundColor: COLOR_ICONO_FONDO }}
            >
              <UserPlus size={18} color={COLOR_MARCA} />
            </span>
            <div>
              <h2 className="h6 fw-bold mb-0" style={{ color: COLOR_NAVY }}>
                Invitar persona al espacio compartido
              </h2>
              <p className="small text-secondary mb-0">
                Envía una invitación por correo electrónico a una cuenta registrada en CloudVault.
              </p>
            </div>
          </div>

          <fieldset disabled={ocupado} className="row g-3 align-items-end mt-1">
            <div className="col-12 col-md-6">
              <label className="form-label small fw-semibold mb-1" style={{ color: '#334155' }}>
                Correo de la cuenta
              </label>
              <input
                type="email"
                className="form-control"
                style={ESTILO_INPUT}
                placeholder="colaborador@empresa.com"
                value={correo}
                required
                maxLength={255}
                onChange={(evento) => setCorreo(evento.target.value)}
              />
            </div>
            <div className="col-12 col-sm-6 col-md-3">
              <label className="form-label small fw-semibold mb-1" style={{ color: '#334155' }}>
                Rol asignado
              </label>
              <select
                className="form-select"
                style={ESTILO_INPUT}
                value={rol}
                onChange={(evento) => setRol(evento.target.value as RolMiembroEditable)}
              >
                {Object.entries(ETIQUETAS_ROL).map(([valor, texto]) => (
                  <option key={valor} value={valor}>{texto}</option>
                ))}
              </select>
            </div>
            <div className="col-12 col-sm-6 col-md-3">
              <button
                type="submit"
                className="btn w-100 text-white fw-semibold d-inline-flex align-items-center justify-content-center gap-2"
                style={{ backgroundColor: COLOR_MARCA, borderRadius: '10px', height: '42px', border: 'none' }}
              >
                <Send size={15} />
                <span>Enviar invitación</span>
              </button>
            </div>
          </fieldset>
        </form>
      )}

      <div style={ESTILO_TARJETA}>
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <div>
            <h2
              className="h5 fw-bold mb-0"
              id={organizacionId ? 'titulo-invitaciones-enviadas' : 'titulo-invitaciones-recibidas'}
              style={{ color: COLOR_NAVY }}
            >
              {organizacionId ? 'Invitaciones enviadas' : 'Invitaciones pendientes'}
            </h2>
            <p className="small text-secondary mb-0">
              {organizacionId
                ? 'Invitaciones activas que has enviado desde esta organización.'
                : 'Invitaciones que otros equipos te han enviado para colaborar.'}
            </p>
          </div>
          <button
            type="button"
            disabled={ocupado || cargandoLista}
            onClick={() => cargar(1)}
            className="btn btn-sm d-inline-flex align-items-center gap-2 fw-semibold"
            style={{
              backgroundColor: COLOR_ICONO_FONDO,
              color: COLOR_MARCA,
              border: '1px solid #DBEAFE',
              borderRadius: '10px',
              padding: '7px 14px',
            }}
          >
            <RefreshCw size={14} style={cargandoLista ? { animation: 'spin 1s linear infinite' } : undefined} />
            <span>Actualizar</span>
          </button>
        </div>

        {mensaje && (
          <div
            role="status"
            className="d-flex align-items-center gap-2 mb-3"
            style={{ backgroundColor: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '12px', padding: '10px 14px', color: '#166534', fontSize: '13px' }}
          >
            <Check size={16} />
            <span>{mensaje}</span>
          </div>
        )}

        {errorAccion && (
          <div
            role="alert"
            className="d-flex align-items-center gap-2 mb-3"
            style={{ backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '12px', padding: '10px 14px', color: '#991B1B', fontSize: '13px' }}
          >
            <span>{errorAccion}</span>
          </div>
        )}

        {errorLista && (
          <div
            role="alert"
            className="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-3"
            style={{ backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '12px', padding: '12px 16px', color: '#991B1B', fontSize: '13px' }}
          >
            <span>{errorLista}</span>
            <button
              type="button"
              className="btn btn-sm fw-semibold"
              style={{ backgroundColor: '#FFFFFF', color: '#991B1B', borderRadius: '8px', border: '1px solid #FCA5A5' }}
              disabled={ocupado}
              onClick={() => cargar(1)}
            >
              Reintentar
            </button>
          </div>
        )}

        {cargandoLista && (
          <div className="d-flex flex-column align-items-center justify-content-center py-5 text-secondary gap-2">
            <Loader2 size={28} color={COLOR_MARCA} style={{ animation: 'spin 1s linear infinite' }} />
            <span role="status" className="small fw-medium">Cargando invitaciones…</span>
          </div>
        )}

        {datos && datos.resultados.length === 0 && (
          <div
            className="d-flex flex-column align-items-center justify-content-center text-center py-5 px-3"
            style={{ backgroundColor: '#F8FAFC', borderRadius: '14px', border: '1px dashed #CBD5E1' }}
          >
            <div
              className="d-inline-flex align-items-center justify-content-center mb-3"
              style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: COLOR_ICONO_FONDO }}
            >
              <Inbox size={22} color={COLOR_MARCA} />
            </div>
            <p className="fw-semibold mb-1" style={{ color: COLOR_NAVY, fontSize: '15px' }}>
              No hay invitaciones pendientes
            </p>
            <p className="small text-secondary mb-0" style={{ maxWidth: '380px' }}>
              {organizacionId
                ? 'Cuando envíes invitaciones a otros miembros de tu equipo aparecerán listadas aquí.'
                : 'Cuando alguien te invite a una organización compartida podrás aceptarla o rechazarla desde aquí.'}
            </p>
          </div>
        )}

        {datos && datos.resultados.length > 0 && (
          <div className="d-flex flex-column gap-2">
            {datos.resultados.map((invitacion) => (
              <div
                key={invitacion.id}
                className="d-flex flex-wrap align-items-center justify-content-between gap-3 p-3"
                style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px' }}
              >
                <div className="d-flex align-items-center gap-3 min-w-0">
                  <span
                    className="d-inline-flex align-items-center justify-content-center flex-shrink-0"
                    style={{ width: '40px', height: '40px', borderRadius: '11px', backgroundColor: COLOR_ICONO_FONDO }}
                  >
                    <Mail size={18} color={COLOR_MARCA} />
                  </span>
                  <div className="min-w-0">
                    <div className="fw-bold text-break" style={{ color: COLOR_NAVY, fontSize: '14px' }}>
                      {invitacion.descripcion}
                    </div>
                    <div className="d-flex flex-wrap align-items-center gap-2 mt-1">
                      <span
                        className="fw-semibold"
                        style={{
                          fontSize: '11px',
                          backgroundColor: COLOR_ICONO_FONDO,
                          color: COLOR_MARCA,
                          borderRadius: '6px',
                          padding: '2px 8px',
                        }}
                      >
                        Rol: {ETIQUETAS_ROL[invitacion.rol]}
                      </span>
                      <span className="d-inline-flex align-items-center gap-1 text-secondary" style={{ fontSize: '12px' }}>
                        <Clock size={12} />
                        Vence el {formatoFecha.format(new Date(invitacion.fechaExpiracion))}
                      </span>
                    </div>
                  </div>
                </div>

                {organizacionId ? (
                  <button
                    type="button"
                    disabled={ocupado}
                    onClick={() => void operar(() => revocarInvitacion(organizacionId, invitacion.id), 'Invitación revocada.')}
                    className="btn btn-sm d-inline-flex align-items-center gap-1 fw-semibold"
                    style={{
                      backgroundColor: '#FEF2F2',
                      color: '#DC2626',
                      border: '1px solid #FECACA',
                      borderRadius: '9px',
                      padding: '6px 12px',
                    }}
                  >
                    <Trash2 size={14} />
                    <span>Revocar</span>
                  </button>
                ) : (
                  <div className="d-flex gap-2">
                    <button
                      type="button"
                      disabled={ocupado}
                      onClick={() => decidir(invitacion.id, 'ACEPTAR')}
                      className="btn btn-sm text-white fw-semibold d-inline-flex align-items-center gap-1"
                      style={{ backgroundColor: COLOR_MARCA, borderRadius: '9px', padding: '6px 14px', border: 'none' }}
                    >
                      <Check size={14} />
                      <span>Aceptar</span>
                    </button>
                    <button
                      type="button"
                      disabled={ocupado}
                      onClick={() => decidir(invitacion.id, 'RECHAZAR')}
                      className="btn btn-sm fw-semibold d-inline-flex align-items-center gap-1"
                      style={{
                        backgroundColor: '#FFFFFF',
                        color: '#475569',
                        border: '1px solid #CBD5E1',
                        borderRadius: '9px',
                        padding: '6px 14px',
                      }}
                    >
                      <X size={14} />
                      <span>Rechazar</span>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {datos && (datos.urlAnterior || datos.urlSiguiente) && (
          <nav className="d-flex justify-content-end gap-2 mt-3" aria-label="Páginas de invitaciones">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              style={{ borderRadius: '8px' }}
              disabled={ocupado || !datos.urlAnterior}
              onClick={() => cargar(consulta.pagina - 1)}
            >
              Anterior
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              style={{ borderRadius: '8px' }}
              disabled={ocupado || !datos.urlSiguiente}
              onClick={() => cargar(consulta.pagina + 1)}
            >
              Siguiente
            </button>
          </nav>
        )}
      </div>
    </section>
  )
}
