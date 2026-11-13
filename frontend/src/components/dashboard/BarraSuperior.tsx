import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, LogOut, Building2, ChevronDown, Plus, Mail, RefreshCw, Check, Home } from 'lucide-react'
import { useOrganizacion } from '../../context/organizacionesContexto'
import { COLOR_MARCA, COLOR_ICONO_FONDO, COLOR_NAVY } from '../../theme/colores'

interface BarraSuperiorProps {
  nombreUsuario: string
  onCerrarSesion: () => void
}

function BarraSuperior({ nombreUsuario, onCerrarSesion }: BarraSuperiorProps) {
  const navegar = useNavigate()
  const {
    organizacion,
    organizaciones,
    seleccionarOrganizacion,
    recargarOrganizaciones,
    abrirCrearOrganizacion,
    ocupadoOrganizacion,
  } = useOrganizacion()

  const [menuAbierto, setMenuAbierto] = useState(false)
  const contenedorMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuAbierto) return
    function manejarClicAfuera(evento: MouseEvent) {
      if (contenedorMenuRef.current && !contenedorMenuRef.current.contains(evento.target as Node)) {
        setMenuAbierto(false)
      }
    }
    function manejarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') setMenuAbierto(false)
    }
    document.addEventListener('mousedown', manejarClicAfuera)
    document.addEventListener('keydown', manejarTecla)
    return () => {
      document.removeEventListener('mousedown', manejarClicAfuera)
      document.removeEventListener('keydown', manejarTecla)
    }
  }, [menuAbierto])

  return (
    <header
      className="d-flex justify-content-between align-items-center px-4 flex-shrink-0 gap-3"
      style={{ height: '64px', backgroundColor: COLOR_NAVY, borderBottom: '1px solid rgba(255,255,255,0.07)' }}
    >
      {/* Selector de organización personalizado + acciones rápidas */}
      <div className="d-flex align-items-center gap-2 min-w-0">
        <div ref={contenedorMenuRef} className="position-relative">
          <button
            type="button"
            disabled={ocupadoOrganizacion}
            aria-haspopup="listbox"
            aria-expanded={menuAbierto}
            onClick={() => setMenuAbierto((actual) => !actual)}
            className="btn d-flex align-items-center gap-2 text-start"
            style={{
              height: '38px',
              backgroundColor: menuAbierto ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.08)',
              border: `1px solid ${menuAbierto ? 'rgba(96,165,250,0.55)' : 'rgba(255,255,255,0.14)'}`,
              borderRadius: '11px',
              padding: '0 12px',
              color: '#FFFFFF',
              boxShadow: menuAbierto ? '0 0 0 3px rgba(37,99,235,0.22)' : 'none',
            }}
          >
            <span
              className="d-inline-flex align-items-center justify-content-center flex-shrink-0"
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '7px',
                backgroundColor: 'rgba(37,99,235,0.25)',
              }}
            >
              <Building2 size={14} color="#60A5FA" />
            </span>
            <span
              className="text-truncate fw-semibold"
              style={{ fontSize: '13px', maxWidth: '210px', color: '#F8FAFC' }}
            >
              {organizacion.nombre}
            </span>
            <ChevronDown
              size={14}
              color="rgba(255,255,255,0.65)"
              style={{
                transform: menuAbierto ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.15s ease',
              }}
            />
          </button>

          {menuAbierto && (
            <div
              role="listbox"
              aria-label="Organizaciones disponibles"
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                left: 0,
                minWidth: '280px',
                maxWidth: '340px',
                backgroundColor: '#1E293B',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: '14px',
                padding: '6px',
                boxShadow: '0 18px 40px rgba(2, 6, 23, 0.45)',
                zIndex: 1080,
              }}
            >
              <div
                className="px-2 py-1 text-uppercase fw-semibold"
                style={{ fontSize: '10.5px', letterSpacing: '0.06em', color: '#94A3B8' }}
              >
                Tus espacios de trabajo
              </div>
              <div className="d-flex flex-column gap-1 my-1" style={{ maxHeight: '240px', overflowY: 'auto' }}>
                {organizaciones.map((org) => {
                  const activa = org.id === organizacion.id
                  const esCompartida = org.tipo === 'COMPARTIDO'
                  return (
                    <button
                      key={org.id}
                      type="button"
                      role="option"
                      aria-selected={activa}
                      onClick={() => {
                        seleccionarOrganizacion(org.id)
                        setMenuAbierto(false)
                      }}
                      className="btn d-flex align-items-center justify-content-between gap-2 w-100 text-start"
                      style={{
                        padding: '8px 10px',
                        borderRadius: '10px',
                        border: 'none',
                        backgroundColor: activa ? 'rgba(37,99,235,0.22)' : 'transparent',
                        color: '#F8FAFC',
                      }}
                    >
                      <div className="d-flex align-items-center gap-2 min-w-0">
                        <span
                          className="d-inline-flex align-items-center justify-content-center flex-shrink-0"
                          style={{
                            width: '28px',
                            height: '28px',
                            borderRadius: '8px',
                            backgroundColor: activa ? COLOR_MARCA : 'rgba(255,255,255,0.08)',
                          }}
                        >
                          <Building2 size={14} color="#FFFFFF" />
                        </span>
                        <div className="min-w-0">
                          <div className="text-truncate fw-semibold" style={{ fontSize: '13px', color: '#FFFFFF' }}>
                            {org.nombre}
                          </div>
                          <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                            {esCompartida ? 'Espacio compartido' : 'Espacio personal'}
                          </div>
                        </div>
                      </div>
                      {activa && <Check size={15} color="#60A5FA" className="flex-shrink-0" />}
                    </button>
                  )
                })}
              </div>

              <div style={{ height: '1px', backgroundColor: 'rgba(255,255,255,0.08)', margin: '6px 4px' }} />

              <div className="d-flex gap-1">
                <button
                  type="button"
                  onClick={() => {
                    setMenuAbierto(false)
                    abrirCrearOrganizacion()
                  }}
                  className="btn d-flex align-items-center gap-2 flex-grow-1 text-start"
                  style={{
                    padding: '8px 10px',
                    borderRadius: '9px',
                    border: 'none',
                    backgroundColor: 'rgba(37,99,235,0.16)',
                    color: '#93C5FD',
                    fontSize: '12.5px',
                    fontWeight: 600,
                  }}
                >
                  <Plus size={14} />
                  <span>Crear nuevo espacio</span>
                </button>
                <button
                  type="button"
                  title="Actualizar lista de espacios"
                  aria-label="Actualizar lista de espacios"
                  onClick={() => void recargarOrganizaciones()}
                  className="btn d-flex align-items-center justify-content-center"
                  style={{
                    width: '36px',
                    borderRadius: '9px',
                    border: 'none',
                    backgroundColor: 'rgba(255,255,255,0.06)',
                    color: '#CBD5E1',
                  }}
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => navegar('/invitaciones')}
          className="btn d-none d-md-inline-flex align-items-center gap-2 flex-shrink-0"
          style={{
            height: '38px',
            borderRadius: '11px',
            border: '1px solid rgba(255,255,255,0.12)',
            backgroundColor: 'rgba(255,255,255,0.08)',
            color: 'rgba(255,255,255,0.9)',
            fontSize: '12.5px',
            fontWeight: 500,
            padding: '0 13px',
          }}
        >
          <Mail size={14} color="#60A5FA" />
          <span>Invitaciones</span>
        </button>

        <button
          type="button"
          onClick={abrirCrearOrganizacion}
          disabled={ocupadoOrganizacion}
          className="btn d-none d-sm-inline-flex align-items-center gap-1 flex-shrink-0 text-white"
          style={{
            height: '38px',
            borderRadius: '11px',
            border: 'none',
            backgroundColor: COLOR_MARCA,
            fontSize: '12.5px',
            fontWeight: 600,
            padding: '0 13px',
          }}
        >
          <Plus size={15} />
          <span>Nuevo espacio</span>
        </button>
      </div>

      {/* Inicio, Perfil y salida */}
      <div className="d-flex align-items-center gap-2">
        <button
          type="button"
          onClick={() => navegar('/')}
          className="btn d-none d-lg-inline-flex align-items-center gap-1 flex-shrink-0"
          title="Ver Landing Page de CloudVault"
          style={{
            height: '36px',
            borderRadius: '10px',
            border: '1px solid rgba(255,255,255,0.12)',
            backgroundColor: 'rgba(255,255,255,0.06)',
            color: 'rgba(255,255,255,0.85)',
            fontSize: '12.5px',
            fontWeight: 500,
            padding: '0 12px',
          }}
        >
          <Home size={14} color="#60A5FA" />
          <span>Inicio</span>
        </button>

        <button
          type="button"
          onClick={() => navegar('/perfil')}
          className="btn d-flex align-items-center gap-2 fw-semibold flex-shrink-0 text-truncate"
          style={{
            backgroundColor: COLOR_ICONO_FONDO,
            color: COLOR_MARCA,
            borderRadius: '50px',
            padding: '4px 14px 4px 4px',
            border: 'none',
            maxWidth: '200px',
          }}
        >
          <span
            className="d-flex align-items-center justify-content-center flex-shrink-0"
            style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#FFFFFF' }}
          >
            <User size={15} color={COLOR_MARCA} />
          </span>
          <span className="text-truncate small">{nombreUsuario}</span>
        </button>

        <button
          type="button"
          className="btn d-flex align-items-center justify-content-center flex-shrink-0"
          style={{ width: '36px', height: '36px', borderRadius: '10px', border: 'none', backgroundColor: '#FFFFFF' }}
          onClick={onCerrarSesion}
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
        >
          <LogOut size={16} color={COLOR_MARCA} />
        </button>
      </div>
    </header>
  )
}

export default BarraSuperior