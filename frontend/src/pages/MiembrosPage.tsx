import { Fragment, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import DashboardLayout from '../components/layout/DashboardLayout'
import { useOrganizacion } from '../context/organizacionesContexto'
import { convertirEnErrorApi, obtenerMensajeDeCampo } from '../services/errorApi'
import {
  cambiarRolMiembro,
  listarMiembros,
  retirarMiembro,
  type MiembroOrganizacion,
  type RolMiembroEditable,
} from '../services/organizacionesService'
import type { Pagina } from '../types/api'
import { formatearFechaCorta } from '../utils/fechas'

const ROLES_EDITABLES: { valor: RolMiembroEditable; etiqueta: string }[] = [
  { valor: 'LECTOR_NV1', etiqueta: 'Lector' },
  { valor: 'OPERATIVO_NV2', etiqueta: 'Operativo' },
  { valor: 'AVANZADO_NV3', etiqueta: 'Avanzado' },
]

type Edicion =
  | { tipo: 'rol'; usuarioId: string; rol: RolMiembroEditable }
  | { tipo: 'retirar'; usuarioId: string }

function etiquetaRol(rol: MiembroOrganizacion['rol']) {
  if (rol === 'PROPIETARIO') return 'Propietario'
  return ROLES_EDITABLES.find((opcion) => opcion.valor === rol)?.etiqueta ?? rol
}

export default function MiembrosPage() {
  const { organizacion, ejecutar, comprobarSeleccion } = useOrganizacion()
  const [consulta, setConsulta] = useState({ pagina: 1 })
  const [datos, setDatos] = useState<Pagina<MiembroOrganizacion> | null>(null)
  const [edicion, setEdicion] = useState<Edicion | null>(null)
  const [errorLista, setErrorLista] = useState('')
  const [errorAccion, setErrorAccion] = useState('')
  const [aviso, setAviso] = useState('')
  const [guardando, setGuardando] = useState(false)
  const guardadoEnCurso = useRef(false)
  const puedeAdministrar = organizacion.nivelRol === 0

  useEffect(() => {
    const controlador = new AbortController()
    void listarMiembros(organizacion.id, consulta.pagina, controlador.signal)
      .then((resultado) => {
        if (!controlador.signal.aborted) setDatos(resultado)
      })
      .catch((causa) => {
        if (!controlador.signal.aborted) setErrorLista(convertirEnErrorApi(causa).message)
      })
    return () => controlador.abort()
  }, [organizacion.id, consulta])

  function pedirPagina(pagina: number) {
    setDatos(null)
    setEdicion(null)
    setErrorLista('')
    setConsulta({ pagina })
  }

  function abrirEdicion(nueva: Edicion) {
    setErrorAccion('')
    setAviso('')
    setEdicion(nueva)
  }

  async function confirmar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!puedeAdministrar || !edicion || guardadoEnCurso.current) return

    guardadoEnCurso.current = true
    setGuardando(true)
    setErrorAccion('')
    try {
      const mensaje = await ejecutar(() => edicion.tipo === 'rol'
        ? cambiarRolMiembro(organizacion.id, edicion.usuarioId, edicion.rol)
        : retirarMiembro(organizacion.id, edicion.usuarioId))
      setAviso(mensaje)
      pedirPagina(edicion.tipo === 'retirar' ? 1 : consulta.pagina)
    } catch (causa) {
      const error = convertirEnErrorApi(causa)
      setErrorAccion(obtenerMensajeDeCampo(error, 'rol') ?? error.message)
      if (error.estadoHttp === 401 || error.estadoHttp === 403 || error.estadoHttp === 404) {
        pedirPagina(1)
        void comprobarSeleccion().catch(() => undefined)
      }
    } finally {
      guardadoEnCurso.current = false
      setGuardando(false)
    }
  }

  return (
    <DashboardLayout seccionActiva="administracion">
      <section className="container-fluid p-3 p-md-4" aria-labelledby="titulo-miembros">
        <Link className="d-lg-none small d-inline-block mb-3" to="/dashboard">Volver a archivos</Link>
        <h1 className="h3 mb-1" id="titulo-miembros">Administración de miembros</h1>
        <p className="text-secondary text-break mb-3">{organizacion.nombre}</p>

        {aviso && <p role="status" className="alert alert-success py-2">{aviso}</p>}
        {errorAccion && <p role="alert" className="alert alert-danger py-2">{errorAccion}</p>}
        {errorLista && (
          <div role="alert" className="alert alert-danger py-2">
            {errorLista}{' '}
            <button type="button" className="btn btn-link btn-sm" onClick={() => pedirPagina(1)}>
              Reintentar desde la primera página
            </button>
          </div>
        )}
        {!datos && !errorLista && <p role="status" className="text-secondary">Cargando miembros…</p>}

        {datos && (
          <>
            <p className="small text-secondary">
              {datos.total === 1 ? '1 miembro' : `${datos.total} miembros`}
            </p>
            {datos.resultados.length > 0 && (
              <div className="table-responsive bg-white rounded border">
                <table className="table align-middle mb-0" aria-label="Miembros de la organización">
                  <thead>
                    <tr>
                      <th scope="col">Persona</th>
                      <th scope="col">Rol</th>
                      <th scope="col">Fecha de ingreso</th>
                      {puedeAdministrar && <th scope="col">Acciones</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {datos.resultados.map((miembro) => {
                      const rol = miembro.rol
                      return (
                        <Fragment key={miembro.usuarioId}>
                          <tr>
                            <th scope="row" className="fw-semibold">
                              <span className="d-block text-break">{miembro.nombreCompleto}</span>
                              <span className="small fw-normal text-secondary text-break">{miembro.correoElectronico}</span>
                            </th>
                            <td>{etiquetaRol(rol)}</td>
                            <td className="text-nowrap">{formatearFechaCorta(miembro.fechaIngreso)}</td>
                            {puedeAdministrar && (
                              <td>
                                {rol !== 'PROPIETARIO' && (
                                  <div className="d-flex flex-wrap gap-2">
                                    <button
                                      type="button" className="btn btn-sm btn-outline-primary" disabled={guardando}
                                      aria-label={`Cambiar rol de ${miembro.nombreCompleto}`}
                                      onClick={() => abrirEdicion({ tipo: 'rol', usuarioId: miembro.usuarioId, rol })}
                                    >Cambiar rol</button>
                                    <button
                                      type="button" className="btn btn-sm btn-outline-danger" disabled={guardando}
                                      aria-label={`Retirar a ${miembro.nombreCompleto}`}
                                      onClick={() => abrirEdicion({ tipo: 'retirar', usuarioId: miembro.usuarioId })}
                                    >Retirar</button>
                                  </div>
                                )}
                              </td>
                            )}
                          </tr>
                          {puedeAdministrar && edicion?.usuarioId === miembro.usuarioId && (
                            <tr>
                              <td colSpan={4}>
                                <form onSubmit={(evento) => void confirmar(evento)}>
                                  <fieldset disabled={guardando} className="d-flex flex-wrap align-items-end gap-2 p-2">
                                    {edicion.tipo === 'rol' ? (
                                      <label className="form-label mb-0">
                                        Nuevo rol de {miembro.nombreCompleto}
                                        <select
                                          className="form-select form-select-sm"
                                          value={edicion.rol}
                                          onChange={(evento) => {
                                            const opcion = ROLES_EDITABLES.find(({ valor }) => valor === evento.target.value)
                                            if (opcion) setEdicion({ ...edicion, rol: opcion.valor })
                                          }}
                                        >
                                          {ROLES_EDITABLES.map(({ valor, etiqueta }) => (
                                            <option key={valor} value={valor}>{etiqueta}</option>
                                          ))}
                                        </select>
                                      </label>
                                    ) : (
                                      <p className="w-100 mb-1">¿Retirar a {miembro.nombreCompleto} de {organizacion.nombre}?</p>
                                    )}
                                    <button
                                      type="submit"
                                      className={`btn btn-sm ${edicion.tipo === 'rol' ? 'btn-primary' : 'btn-danger'}`}
                                      disabled={edicion.tipo === 'rol' && edicion.rol === rol}
                                    >{edicion.tipo === 'rol' ? 'Guardar rol' : 'Confirmar retirada'}</button>
                                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setEdicion(null)}>
                                      Cancelar
                                    </button>
                                    {guardando && <span role="status" className="small">Guardando…</span>}
                                  </fieldset>
                                </form>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {(datos.urlAnterior || datos.urlSiguiente) && (
              <nav aria-label="Páginas de miembros" className="d-flex align-items-center gap-2 mt-3">
                <button
                  type="button" className="btn btn-sm btn-outline-secondary"
                  disabled={!datos.urlAnterior || guardando} onClick={() => pedirPagina(consulta.pagina - 1)}
                >Anterior</button>
                <span className="small">Página {consulta.pagina}</span>
                <button
                  type="button" className="btn btn-sm btn-outline-secondary"
                  disabled={!datos.urlSiguiente || guardando} onClick={() => pedirPagina(consulta.pagina + 1)}
                >Siguiente</button>
              </nav>
            )}
          </>
        )}
      </section>
    </DashboardLayout>
  )
}
