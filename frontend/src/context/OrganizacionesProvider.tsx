import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Building2, Loader2, Plus, RefreshCw, X } from 'lucide-react'
import { listarOrganizacionesDisponibles, type OrganizacionDisponible } from '../services/organizacionesService'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../services/errorApi'
import { crearOrganizacionCompartida } from '../services/invitacionesService'
import { cerrarSesionEnServidor } from '../services/authService'
import { COLOR_FONDO_PAGINA, COLOR_ICONO_FONDO, COLOR_MARCA, COLOR_NAVY } from '../theme/colores'
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
      setSeleccion((actual) => (actual && lista.some((o) => o.id === actual) ? actual : lista[0]?.id ?? null))
      return lista
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
      setOrganizaciones([])
      setSeleccion(null)
      throw causa
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    let vigente = true
    void listarOrganizacionesDisponibles()
      .then((lista) => {
        if (!vigente) return
        setOrganizaciones(lista)
        setSeleccion((actual) => (actual && lista.some((o) => o.id === actual) ? actual : lista[0]?.id ?? null))
      })
      .catch((causa) => {
        if (vigente) setError(convertirEnErrorApi(causa).message)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [])

  const comprobarSeleccion = useCallback(async () => {
    const lista = await cargar()
    return lista.some((o) => o.id === seleccion)
  }, [cargar, seleccion])

  const ejecutar = useCallback(async <T,>(accion: () => Promise<T>): Promise<T> => {
    operaciones.current += 1
    setPendientes(operaciones.current)
    try {
      return await accion()
    } finally {
      operaciones.current -= 1
      setPendientes(operaciones.current)
    }
  }, [])

  const seleccionarOrganizacion = useCallback((id: string) => {
    if (!operaciones.current && id) setSeleccion(id)
  }, [])

  const recargarOrganizaciones = useCallback(async () => {
    await cargar().catch(() => undefined)
  }, [cargar])

  const abrirCrearOrganizacion = useCallback(() => {
    setErrorCreacion('')
    setCreacion({ id: crypto.randomUUID(), nombre: '' })
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
      const errorApi = convertirEnErrorApi(causa)
      setErrorCreacion(obtenerMensajeDeCampo(errorApi, 'nombre') ?? errorApi.message)
    } finally {
      creando.current = false
    }
  }

  const organizacion = organizaciones.find((o) => o.id === seleccion) ?? organizaciones[0]

  return (
    <div style={{ height: '100vh', width: '100%', overflow: 'hidden', backgroundColor: COLOR_FONDO_PAGINA }}>
      {cargando ? (
        <div className="d-flex flex-column align-items-center justify-content-center h-100 gap-3" style={{ color: '#64748B' }}>
          <Loader2 size={32} color={COLOR_MARCA} style={{ animation: 'spin 1s linear infinite' }} />
          <p role="status" className="mb-0 fw-medium">Cargando tu espacio de trabajo…</p>
        </div>
      ) : error || !organizacion ? (
        <div className="d-flex flex-column align-items-center justify-content-center h-100 p-4">
          <div
            className="bg-white p-4 text-center"
            style={{ maxWidth: 440, width: '100%', borderRadius: 20, border: '1px solid #E2E8F0', boxShadow: '0 8px 24px rgba(15,23,42,0.06)' }}
          >
            <div
              className="d-inline-flex align-items-center justify-content-center mb-3"
              style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: COLOR_ICONO_FONDO }}
            >
              <Building2 size={24} color={COLOR_MARCA} />
            </div>
            <h2 className="h5 fw-bold mb-2" style={{ color: COLOR_NAVY }}>
              {error ? 'No se pudo cargar tu organización' : 'Selecciona una organización'}
            </h2>
            {error && <p role="alert" className="small text-danger mb-3">{error}</p>}
            {!error && organizaciones.length > 0 && (
              <select
                className="form-select mb-3"
                value={seleccion ?? ''}
                onChange={(e) => setSeleccion(e.target.value || null)}
                style={{ borderRadius: 10 }}
              >
                <option value="">Selecciona una organización…</option>
                {organizaciones.map((org) => (
                  <option key={org.id} value={org.id}>{org.nombre}</option>
                ))}
              </select>
            )}
            <div className="d-flex justify-content-center gap-2">
              <button
                type="button"
                className="btn btn-sm d-inline-flex align-items-center gap-2 text-white fw-semibold px-3 py-2"
                style={{ backgroundColor: COLOR_MARCA, borderRadius: 10, border: 'none' }}
                onClick={() => void recargarOrganizaciones()}
              >
                <RefreshCw size={15} /> Reintentar
              </button>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary px-3 py-2"
                style={{ borderRadius: 10 }}
                onClick={() => {
                  void cerrarSesionEnServidor().finally(() => { window.location.href = '/login' })
                }}
              >
                Cerrar sesión
              </button>
            </div>
          </div>
        </div>
      ) : (
        <OrganizacionesContexto.Provider
          key={organizacion.id}
          value={{
            organizacion,
            organizaciones,
            seleccionarOrganizacion,
            recargarOrganizaciones,
            abrirCrearOrganizacion,
            ocupadoOrganizacion: pendientes > 0,
            comprobarSeleccion,
            ejecutar,
          }}
        >
          {children}
        </OrganizacionesContexto.Provider>
      )}

      {creacion && (
        <div
          className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
          style={{ backgroundColor: 'rgba(15, 23, 42, 0.55)', backdropFilter: 'blur(3px)', zIndex: 1070 }}
          onClick={() => pendientes === 0 && setCreacion(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-crear-organizacion"
            className="bg-white w-100"
            style={{ maxWidth: 440, borderRadius: 20, padding: 24, margin: '0 16px', boxShadow: '0 20px 50px rgba(15,23,42,0.2)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="d-flex justify-content-between align-items-center mb-2">
              <div className="d-flex align-items-center gap-2">
                <span
                  className="d-inline-flex align-items-center justify-content-center"
                  style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: COLOR_ICONO_FONDO }}
                >
                  <Building2 size={18} color={COLOR_MARCA} />
                </span>
                <h5 id="titulo-crear-organizacion" className="fw-bold mb-0" style={{ color: COLOR_NAVY }}>
                  Nueva organización
                </h5>
              </div>
              <button
                type="button"
                className="btn btn-sm p-1"
                onClick={() => setCreacion(null)}
                disabled={pendientes > 0}
                aria-label="Cerrar"
              >
                <X size={20} color="#64748B" />
              </button>
            </div>
            <p className="small text-secondary mb-3">
              Crea un espacio compartido para colaborar con otros miembros de tu equipo en CloudVault.
            </p>
            <form onSubmit={(evento) => void crearCompartida(evento)}>
              <fieldset disabled={pendientes > 0}>
                <label htmlFor="nombre-nueva-org" className="form-label small fw-semibold mb-1" style={{ color: '#334155' }}>
                  Nombre de la organización
                </label>
                <input
                  id="nombre-nueva-org"
                  className="form-control mb-3"
                  style={{ backgroundColor: COLOR_ICONO_FONDO, border: '1px solid #DBEAFE', borderRadius: 10, padding: '10px 14px' }}
                  placeholder="Ej. Equipo de Ingeniería"
                  required
                  maxLength={150}
                  autoFocus
                  value={creacion.nombre}
                  onChange={(evento) => setCreacion({ ...creacion, nombre: evento.target.value })}
                />
                {errorCreacion && (
                  <p className="text-danger small mb-3" role="alert">
                    {errorCreacion}
                  </p>
                )}
                <div className="d-flex justify-content-end gap-2">
                  <button
                    type="button"
                    className="btn btn-light fw-medium px-3"
                    style={{ borderRadius: 50 }}
                    onClick={() => setCreacion(null)}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="btn text-white fw-semibold d-inline-flex align-items-center gap-2 px-4"
                    style={{ backgroundColor: COLOR_MARCA, borderRadius: 50, border: 'none' }}
                  >
                    {pendientes > 0 ? (
                      <>
                        <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> Creando…
                      </>
                    ) : (
                      <>
                        <Plus size={16} /> Crear espacio
                      </>
                    )}
                  </button>
                </div>
              </fieldset>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
