import { useState } from 'react'
import { Edit, Mail, MoreVertical, UserPlus } from 'lucide-react'
import type { MiembroOrganizacion } from '../../types/administracion'
import { obtenerIniciales } from '../../utils/administracion'
import { COLOR_MARCA, COLOR_NAVY } from '../../theme/colores'
import InsigniaRol from './InsigniaRol'
import IndicadorEstado from './IndicadorEstado'

const ENCABEZADOS = ['USUARIO', 'ROL', 'ESTADO', 'ACCIONES']

const ESTILO_BOTON_ACCION: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  fontSize: 11,
  fontWeight: 600,
  borderRadius: 8,
  padding: '5px 10px',
}

interface TablaMiembrosProps {
  miembros: MiembroOrganizacion[]
  onInvitar: () => void
  onEditar: (miembro: MiembroOrganizacion) => void
  onReenviar: (miembro: MiembroOrganizacion) => void
  onQuitar: (miembro: MiembroOrganizacion) => void
}

function TablaMiembros({ miembros, onInvitar, onEditar, onReenviar, onQuitar }: TablaMiembrosProps) {
  const [idMenuAbierto, setIdMenuAbierto] = useState<string | null>(null)

  function ejecutarDesdeMenu(accion: () => void) {
    setIdMenuAbierto(null)
    accion()
  }

  return (
    <section
      style={{
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 14,
        boxShadow: '0 1px 3px rgba(15,23,42,0.04)',
      }}
    >
      <header className="d-flex align-items-center justify-content-between gap-2" style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0' }}>
        <div>
          <h2 className="mb-1" style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Usuarios y permisos de la organización</h2>
          <p className="mb-0" style={{ fontSize: 12, color: '#94A3B8' }}>Control de acceso basado en roles (RBAC)</p>
        </div>
        <button
          type="button"
          onClick={onInvitar}
          className="btn d-flex align-items-center gap-2 text-white flex-shrink-0"
          style={{ backgroundColor: COLOR_MARCA, borderRadius: 10, padding: '8px 14px', fontWeight: 600, fontSize: 12 }}
        >
          <UserPlus size={13} strokeWidth={2} />
          Invitar usuario
        </button>
      </header>

      <div style={{ overflowX: 'auto' }}>
        <table className="w-100" style={{ borderCollapse: 'collapse', minWidth: 560 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #E2E8F0', background: '#F8FAFC' }}>
              {ENCABEZADOS.map((encabezado, indice) => (
                <th
                  key={encabezado}
                  style={{
                    padding: '10px 20px',
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#94A3B8',
                    letterSpacing: '0.06em',
                    textAlign: indice === ENCABEZADOS.length - 1 ? 'right' : 'left',
                  }}
                >
                  {encabezado}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {miembros.map((miembro, indice) => {
              const esPropietario = miembro.rol === 'propietario'
              const estaPendiente = miembro.estado === 'pendiente'
              return (
                <tr key={miembro.id} style={{ borderBottom: indice < miembros.length - 1 ? '1px solid #F1F5F9' : 'none' }}>
                  <td style={{ padding: '14px 20px' }}>
                    <div className="d-flex align-items-center gap-2">
                      <div
                        className="d-flex align-items-center justify-content-center flex-shrink-0"
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: '50%',
                          background: estaPendiente ? '#F1F5F9' : COLOR_NAVY,
                          color: estaPendiente ? '#94A3B8' : '#fff',
                          fontWeight: 700,
                          fontSize: 12,
                        }}
                      >
                        {obtenerIniciales(miembro.nombreCompleto)}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <p className="mb-0" style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{miembro.nombreCompleto}</p>
                        <p className="mb-0" style={{ fontSize: 11, color: '#94A3B8' }}>{miembro.correoElectronico}</p>
                      </div>
                    </div>
                  </td>

                  <td style={{ padding: '14px 20px' }}>
                    <InsigniaRol rol={miembro.rol} />
                  </td>

                  <td style={{ padding: '14px 20px' }}>
                    <IndicadorEstado estado={miembro.estado} />
                  </td>

                  <td style={{ padding: '14px 20px', textAlign: 'right' }}>
                    {esPropietario ? (
                      <span style={{ fontSize: 11, color: '#94A3B8' }}>—</span>
                    ) : (
                      <div className="d-inline-flex align-items-center gap-2">
                        {estaPendiente ? (
                          <button
                            type="button"
                            onClick={() => onReenviar(miembro)}
                            className="btn"
                            style={{ ...ESTILO_BOTON_ACCION, color: '#D97706', background: 'rgba(217,119,6,0.07)', border: '1px solid rgba(217,119,6,0.2)' }}
                          >
                            <Mail size={12} strokeWidth={1.9} />
                            Reenviar
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => onEditar(miembro)}
                            className="btn"
                            style={{ ...ESTILO_BOTON_ACCION, color: COLOR_MARCA, background: 'rgba(37,99,235,0.07)', border: '1px solid rgba(37,99,235,0.18)' }}
                          >
                            <Edit size={12} strokeWidth={1.9} />
                            Editar
                          </button>
                        )}

                        <div style={{ position: 'relative' }}>
                          <button
                            type="button"
                            aria-label={`Más acciones para ${miembro.nombreCompleto}`}
                            aria-expanded={idMenuAbierto === miembro.id}
                            onClick={() => setIdMenuAbierto(idMenuAbierto === miembro.id ? null : miembro.id)}
                            className="btn d-flex align-items-center"
                            style={{ border: '1px solid #E2E8F0', borderRadius: 8, padding: '5px 6px', color: '#64748B' }}
                          >
                            <MoreVertical size={13} strokeWidth={1.9} />
                          </button>

                          {idMenuAbierto === miembro.id && (
                            <>
                              <div
                                onClick={() => setIdMenuAbierto(null)}
                                style={{ position: 'fixed', inset: 0, zIndex: 40 }}
                                aria-hidden="true"
                              />
                              <div
                                role="menu"
                                style={{
                                  position: 'absolute',
                                  right: 0,
                                  top: 'calc(100% + 4px)',
                                  background: '#fff',
                                  border: '1px solid #E2E8F0',
                                  borderRadius: 10,
                                  boxShadow: '0 8px 24px rgba(15,23,42,0.1)',
                                  zIndex: 50,
                                  minWidth: 200,
                                  overflow: 'hidden',
                                  textAlign: 'left',
                                }}
                              >
                                {!estaPendiente && (
                                  <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => ejecutarDesdeMenu(() => onEditar(miembro))}
                                    className="btn d-block w-100 text-start"
                                    style={{ padding: '9px 14px', fontSize: 12, color: '#374151', borderRadius: 0 }}
                                  >
                                    Cambiar rol
                                  </button>
                                )}
                                <button
                                  type="button"
                                  role="menuitem"
                                  onClick={() => ejecutarDesdeMenu(() => onQuitar(miembro))}
                                  className="btn d-block w-100 text-start"
                                  style={{ padding: '9px 14px', fontSize: 12, color: '#DC2626', borderRadius: 0, borderTop: estaPendiente ? 'none' : '1px solid #F1F5F9' }}
                                >
                                  {estaPendiente ? 'Cancelar invitación' : 'Quitar de la organización'}
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default TablaMiembros