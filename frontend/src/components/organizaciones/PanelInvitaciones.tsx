import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  decidirInvitacion,
  enviarInvitacion,
  listarInvitaciones,
  revocarInvitacion,
  type DecisionInvitacion,
} from '../../services/invitacionesService'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../../services/errorApi'
import type { RolMiembroEditable } from '../../services/organizacionesService'

const ETIQUETAS_ROL: Record<RolMiembroEditable, string> = {
  LECTOR_NV1: 'Lector',
  OPERATIVO_NV2: 'Operativo',
  AVANZADO_NV3: 'Avanzado',
}
const formatoFecha = new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium', timeStyle: 'short' })

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
      .then((lista) => { if (!controlador.signal.aborted) setDatos(lista) })
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
    void operar(() => enviarInvitacion(organizacionId, correo.trim(), rol), 'Invitación enviada.', () => setCorreo(''))
  }

  function decidir(id: string, decision: DecisionInvitacion) {
    const acepta = decision === 'ACEPTAR'
    void operar(
      () => decidirInvitacion(id, decision),
      acepta ? 'Invitación aceptada. Puedes entrar desde el selector de organizaciones.' : 'Invitación rechazada.',
    )
  }

  return (
    <section aria-labelledby="invitaciones-pendientes">
      {organizacionId && (
        <form onSubmit={enviar} className="border rounded bg-white p-3 mb-3">
          <h2 className="h5">Invitar persona</h2>
          <p className="small text-secondary">Invita a una cuenta de CloudVault por su correo. Podrá entrar cuando acepte, con el rol seleccionado.</p>
          <fieldset disabled={ocupado} className="d-flex flex-wrap align-items-end gap-3">
            <label className="form-label mb-0">
              Correo de la cuenta
              <input
                type="email" className="form-control" value={correo} required maxLength={255}
                onChange={(evento) => setCorreo(evento.target.value)}
              />
            </label>
            <label className="form-label mb-0">
              Rol de la invitación
              <select
                className="form-select" value={rol}
                onChange={(evento) => setRol(evento.target.value as RolMiembroEditable)}
              >
                {Object.entries(ETIQUETAS_ROL).map(([valor, texto]) => (
                  <option key={valor} value={valor}>{texto}</option>
                ))}
              </select>
            </label>
            <button type="submit" className="btn btn-primary">Enviar invitación</button>
          </fieldset>
        </form>
      )}

      <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
        <h2 className="h5 mb-0" id="invitaciones-pendientes">{organizacionId ? 'Invitaciones enviadas' : 'Invitaciones pendientes'}</h2>
        <button type="button" className="btn btn-sm btn-outline-secondary" disabled={ocupado}
          onClick={() => cargar(1)}>Actualizar invitaciones</button>
      </div>
      {mensaje && <p role="status" className="alert alert-success py-2">{mensaje}</p>}
      {errorAccion && <p role="alert" className="alert alert-danger py-2">{errorAccion}</p>}
      {errorLista && (
        <p role="alert" className="alert alert-danger py-2">
          {errorLista}{' '}
          <button type="button" className="btn btn-link btn-sm" disabled={ocupado} onClick={() => cargar(1)}>Reintentar</button>
        </p>
      )}
      {!datos && !errorLista && <p role="status">Cargando invitaciones…</p>}
      {datos && (datos.resultados.length === 0 ? <p className="text-secondary">No hay invitaciones pendientes.</p> : (
        <ul className="list-group">
          {datos.resultados.map((invitacion) => (
            <li key={invitacion.id} className="list-group-item d-flex flex-wrap align-items-center justify-content-between gap-2">
              <div>
                <div className="fw-semibold text-break">{invitacion.descripcion}</div>
                <small className="text-secondary">
                  {ETIQUETAS_ROL[invitacion.rol]} · Vence el {formatoFecha.format(new Date(invitacion.fechaExpiracion))}
                </small>
              </div>
              {organizacionId ? (
                <button
                  type="button" className="btn btn-sm btn-outline-danger" disabled={ocupado}
                  onClick={() => void operar(() => revocarInvitacion(organizacionId, invitacion.id), 'Invitación revocada.')}
                >Revocar</button>
              ) : (
                <div className="d-flex gap-2">
                  <button type="button" className="btn btn-sm btn-primary" disabled={ocupado}
                    onClick={() => decidir(invitacion.id, 'ACEPTAR')}>Aceptar</button>
                  <button type="button" className="btn btn-sm btn-outline-secondary" disabled={ocupado}
                    onClick={() => decidir(invitacion.id, 'RECHAZAR')}>Rechazar</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      ))}
      {datos && (datos.urlAnterior || datos.urlSiguiente) && (
        <nav className="d-flex gap-2 mt-2" aria-label="Páginas de invitaciones">
          <button type="button" className="btn btn-sm btn-outline-secondary" disabled={ocupado || !datos.urlAnterior}
            onClick={() => cargar(consulta.pagina - 1)}>Anterior</button>
          <button type="button" className="btn btn-sm btn-outline-secondary" disabled={ocupado || !datos.urlSiguiente}
            onClick={() => cargar(consulta.pagina + 1)}>Siguiente</button>
        </nav>
      )}
    </section>
  )
}
