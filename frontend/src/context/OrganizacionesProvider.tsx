import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { listarOrganizacionesDisponibles, type OrganizacionDisponible } from '../services/organizacionesService'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../services/errorApi'
import { crearOrganizacionCompartida } from '../services/invitacionesService'
import { cerrarSesionEnServidor } from '../services/authService'
import { OrganizacionesContexto } from './organizacionesContexto'

export default function OrganizacionesProvider({ children }: { children: ReactNode }) {
  const [organizaciones, setOrganizaciones] = useState<OrganizacionDisponible[]>([])
  const [seleccion, setSeleccion] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [pendientes, setPendientes] = useState(0)
  const operaciones = useRef(0)
  const [creacion, setCreacion] = useState<{ id: string; nombre: string } | null>(null)
  const [errorCreacion, setErrorCreacion] = useState('')
  const creando = useRef(false)

  const cargar = useCallback(async () => {
    setError('')
    try {
      const lista = await listarOrganizacionesDisponibles()
      setOrganizaciones(lista)
      setSeleccion((actual) => actual && lista.some((o) => o.id === actual) ? actual : lista.length === 1 ? lista[0].id : null)
      return lista
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
      setOrganizaciones([])
      setSeleccion(null)
      throw causa
    } finally { setCargando(false) }
  }, [])

  useEffect(() => {
    let vigente = true
    void listarOrganizacionesDisponibles().then((lista) => {
      if (!vigente) return
      setOrganizaciones(lista)
      setSeleccion(lista.length === 1 ? lista[0].id : null)
    }).catch((causa) => {
      if (vigente) setError(convertirEnErrorApi(causa).message)
    }).finally(() => { if (vigente) setCargando(false) })
    return () => { vigente = false }
  }, [])

  const comprobarSeleccion = useCallback(async () => {
    const lista = await cargar()
    return lista.some((o) => o.id === seleccion)
  }, [cargar, seleccion])

  const ejecutar = useCallback(async <T,>(accion: () => Promise<T>): Promise<T> => {
    operaciones.current += 1
    setPendientes(operaciones.current)
    try { return await accion() }
    finally {
      operaciones.current -= 1
      setPendientes(operaciones.current)
    }
  }, [])

  async function crearCompartida(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!creacion || creando.current) return
    creando.current = true
    setErrorCreacion('')
    try {
      await ejecutar(async () => {
        await crearOrganizacionCompartida(creacion.id, creacion.nombre.trim())
        await cargar()
        setSeleccion(creacion.id)
        setCreacion(null)
      })
    } catch (causa) {
      const error = convertirEnErrorApi(causa)
      setErrorCreacion(obtenerMensajeDeCampo(error, 'nombre') ?? error.message)
    } finally {
      creando.current = false
    }
  }

  const organizacion = organizaciones.find((o) => o.id === seleccion)
  return <div className="d-flex flex-column" style={{ height: '100vh' }}>
    <div className="d-flex flex-wrap align-items-center gap-2 px-3 py-2 border-bottom bg-white flex-shrink-0">
      <label htmlFor="organizacion-activa">Organización</label>
      <select id="organizacion-activa" className="form-select form-select-sm" style={{ maxWidth: 360 }}
        value={seleccion ?? ''} disabled={cargando || pendientes > 0}
        onChange={(evento) => { if (!operaciones.current) setSeleccion(evento.target.value || null) }}>
        <option value="">Selecciona una organización</option>
        {organizaciones.map((org) => <option key={org.id} value={org.id}>{org.nombre}</option>)}
      </select>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={cargando || pendientes > 0}
        onClick={() => { void cargar().catch(() => undefined) }}>Actualizar</button>
      <Link className="btn btn-sm btn-outline-secondary" to="/invitaciones">Invitaciones</Link>
      <button type="button" className="btn btn-sm btn-outline-primary" disabled={cargando || pendientes > 0}
        onClick={() => { setErrorCreacion(''); setCreacion({ id: crypto.randomUUID(), nombre: '' }) }}>
        Crear organización
      </button>
      {organizacion && (
        <Link className="btn btn-sm btn-outline-secondary d-lg-none" to="/organizacion/miembros">
          Miembros
        </Link>
      )}
      {pendientes > 0 && <span role="status" className="small">Operación en curso…</span>}
      <button type="button" className="btn btn-sm ms-auto" onClick={() => {
        void cerrarSesionEnServidor().finally(() => { window.location.href = '/login' })
      }}>Salir</button>
    </div>
    {creacion && (
      <form className="border-bottom bg-white px-3 py-2" onSubmit={(evento) => void crearCompartida(evento)}>
        <fieldset className="d-flex flex-wrap align-items-end gap-2" disabled={pendientes > 0}>
          <label className="form-label mb-0">
            Nombre de la organización compartida
            <input className="form-control form-control-sm" required maxLength={150} value={creacion.nombre}
              onChange={(evento) => setCreacion({ ...creacion, nombre: evento.target.value })} />
          </label>
          <button type="submit" className="btn btn-sm btn-primary">Crear</button>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setCreacion(null)}>Cancelar</button>
        </fieldset>
        {errorCreacion && <p className="text-danger small mb-0" role="alert">{errorCreacion}</p>}
      </form>
    )}
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
      {cargando ? <p role="status" className="p-3">Cargando organizaciones…</p>
        : error ? <p role="alert" className="p-3 text-danger">{error}</p>
        : organizacion ? <OrganizacionesContexto.Provider key={organizacion.id}
          value={{ organizacion, comprobarSeleccion, ejecutar }}>{children}</OrganizacionesContexto.Provider>
        : <p className="p-3">{organizaciones.length ? 'Selecciona la organización cuyos archivos quieres ver.' : 'No tienes organizaciones disponibles.'}</p>}
    </div>
  </div>
}
