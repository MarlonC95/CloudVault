import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { listarOrganizacionesDisponibles, type OrganizacionDisponible } from '../services/organizacionesService'
import { convertirEnErrorApi } from '../services/errorApi'
import { cerrarSesionEnServidor } from '../services/authService'
import { OrganizacionesContexto } from './organizacionesContexto'

export default function OrganizacionesProvider({ children }: { children: ReactNode }) {
  const [organizaciones, setOrganizaciones] = useState<OrganizacionDisponible[]>([])
  const [seleccion, setSeleccion] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [pendientes, setPendientes] = useState(0)
  const operaciones = useRef(0)

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

  const organizacion = organizaciones.find((o) => o.id === seleccion)
  return <div className="d-flex flex-column" style={{ height: '100vh' }}>
    <div className="d-flex align-items-center gap-2 px-3 py-2 border-bottom bg-white flex-shrink-0">
      <label htmlFor="organizacion-activa">Organización</label>
      <select id="organizacion-activa" className="form-select form-select-sm" style={{ maxWidth: 360 }}
        value={seleccion ?? ''} disabled={cargando || pendientes > 0}
        onChange={(evento) => { if (!operaciones.current) setSeleccion(evento.target.value || null) }}>
        <option value="">Selecciona una organización</option>
        {organizaciones.map((org) => <option key={org.id} value={org.id}>{org.nombre}</option>)}
      </select>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={cargando || pendientes > 0}
        onClick={() => { void cargar().catch(() => undefined) }}>Actualizar</button>
      {pendientes > 0 && <span role="status" className="small">Operación en curso…</span>}
      <button type="button" className="btn btn-sm ms-auto" onClick={() => {
        void cerrarSesionEnServidor().finally(() => { window.location.href = '/login' })
      }}>Salir</button>
    </div>
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
      {cargando ? <p role="status" className="p-3">Cargando organizaciones…</p>
        : error ? <p role="alert" className="p-3 text-danger">{error}</p>
        : organizacion ? <OrganizacionesContexto.Provider key={organizacion.id}
          value={{ organizacion, comprobarSeleccion, ejecutar }}>{children}</OrganizacionesContexto.Provider>
        : <p className="p-3">{organizaciones.length ? 'Selecciona la organización cuyos archivos quieres ver.' : 'No tienes organizaciones disponibles.'}</p>}
    </div>
  </div>
}
