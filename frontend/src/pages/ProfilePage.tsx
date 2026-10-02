import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronRight,
  Edit,
  User,
  Mail,
  Shield,
  HardDrive,
  Lock,
  KeyRound,
  Zap,
  Activity,
  Upload,
  Users,
  Download,
} from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import { obtenerSesion } from '../services/authService'

const CATEGORIAS_ALMACENAMIENTO = [
  { etiqueta: 'Documentos', tamano: '18 GB', color: '#2563EB' },
  { etiqueta: 'Backups', tamano: '21 GB', color: '#7C3AED' },
  { etiqueta: 'Otros', tamano: '6 GB', color: '#0891B2' },
]

const ACTIVIDAD_RECIENTE = [
  { accion: 'Archivo subido', archivo: 'Arquitectura_PaaS_v1.pdf', tiempo: 'Hace 2h', icono: <Upload size={13} color="#2563EB" strokeWidth={2} /> },
  { accion: 'Compartido con equipo', archivo: 'Proyectos_2026', tiempo: 'Ayer', icono: <Users size={13} color="#16A34A" strokeWidth={2} /> },
  { accion: 'Descarga', archivo: 'Respaldo_BaseDatos.zip', tiempo: '30 Ago', icono: <Download size={13} color="#64748B" strokeWidth={2} /> },
]

function ProfilePage() {
  const navegar = useNavigate()
  const usuario = obtenerSesion()?.usuario

  const [modoEdicion, setModoEdicion] = useState(false)
  const [cambiandoContrasena, setCambiandoContrasena] = useState(false)
  const [dosFactores, setDosFactores] = useState(true)
  const [modificandoPalabraSecreta, setModificandoPalabraSecreta] = useState(false)
  const [palabraSecreta, setPalabraSecreta] = useState('')
  const [nombre, setNombre] = useState(usuario?.nombreCompleto ?? '')
  const [correo, setCorreo] = useState(usuario?.correoElectronico ?? '')

  const almacenamientoUsado = 45
  const almacenamientoTotal = 100

  const iniciales = nombre
    .split(' ')
    .map((palabra) => palabra[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  function alternarEdicion() {
    // TODO(backend): al guardar, llamar a PATCH /api/auth/perfil/ con { nombre, correo }
    setModoEdicion((valor) => !valor)
  }

  const campos = [
    { etiqueta: 'Nombre Completo', valor: nombre, icono: <User size={14} color="#94A3B8" strokeWidth={1.8} />, editable: true, onCambiar: setNombre },
    { etiqueta: 'Correo Electrónico', valor: correo, icono: <Mail size={14} color="#94A3B8" strokeWidth={1.8} />, editable: true, onCambiar: setCorreo },
    { etiqueta: 'Rol en el Sistema', valor: 'Desarrollador / Admin', icono: <Shield size={14} color="#94A3B8" strokeWidth={1.8} />, editable: false },
    { etiqueta: 'Nivel de Almacenamiento', valor: '100 GB (Pro PaaS)', icono: <HardDrive size={14} color="#94A3B8" strokeWidth={1.8} />, editable: false },
  ]

  return (
    <DashboardLayout>
      <div style={{ padding: '36px 28px' }}>
        <button
          type="button"
          onClick={() => navegar('/dashboard')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#64748B',
            fontSize: 13,
            fontWeight: 500,
            marginBottom: 24,
            padding: 0,
          }}
        >
          <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />
          Volver al Explorador
        </button>

        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#0F172A', marginBottom: 4, letterSpacing: '-0.015em' }}>
          Perfil de Usuario
        </h1>
        <p style={{ fontSize: 14, color: '#64748B', marginBottom: 28 }}>
          Gestiona tu información personal, seguridad y preferencias.
        </p>

        {/* Tarjeta de identidad */}
        <div
          style={{
            background: '#fff',
            border: '1px solid #E2E8F0',
            borderRadius: 16,
            overflow: 'hidden',
            marginBottom: 16,
            boxShadow: '0 1px 6px rgba(15,23,42,0.05)',
          }}
        >
          <div
            style={{
              height: 110,
              background: 'linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%)',
              position: 'relative',
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: 0,
                backgroundImage: 'radial-gradient(circle, rgba(37,99,235,0.22) 1px, transparent 1px)',
                backgroundSize: '18px 18px',
              }}
            />
          </div>

          <div style={{ padding: '0 28px 28px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16 }}>
                <div
                  style={{
                    width: 76,
                    height: 76,
                    borderRadius: '50%',
                    background: '#2563EB',
                    border: '4px solid #fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    fontWeight: 800,
                    fontSize: 26,
                    marginTop: -42,
                    flexShrink: 0,
                    boxShadow: '0 2px 12px rgba(37,99,235,0.35)',
                    letterSpacing: '-0.02em',
                    position: 'relative',
                    zIndex: 1,
                  }}
                >
                  {iniciales || 'US'}
                </div>
                <div style={{ paddingBottom: 2 }}>
                  <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', margin: 0 }}>{nombre}</h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                    <span style={{ fontSize: 12, color: '#64748B' }}>Desarrollador / Admin</span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: '#fff',
                        background: '#16A34A',
                        borderRadius: 20,
                        padding: '2px 8px',
                        letterSpacing: '0.04em',
                      }}
                    >
                      Plan Pro Activo
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={alternarEdicion}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 14px',
                  background: modoEdicion ? '#2563EB' : '#F8FAFC',
                  color: modoEdicion ? '#fff' : '#374151',
                  border: '1px solid #E2E8F0',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 500,
                }}
              >
                <Edit size={14} strokeWidth={1.9} />
                {modoEdicion ? 'Guardar' : 'Editar perfil'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid #F1F5F9' }}>
              {campos.map((campo, indice) => (
                <div
                  key={campo.etiqueta}
                  style={{
                    padding: '16px 0',
                    borderBottom: indice < 2 ? '1px solid #F1F5F9' : 'none',
                    paddingRight: indice % 2 === 0 ? 24 : 0,
                    paddingLeft: indice % 2 === 1 ? 24 : 0,
                    borderLeft: indice % 2 === 1 ? '1px solid #F1F5F9' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                    {campo.icono}
                    <span style={{ fontSize: 11, color: '#94A3B8', fontWeight: 500 }}>{campo.etiqueta}</span>
                  </div>
                  {modoEdicion && campo.editable ? (
                    <input
                      value={campo.valor}
                      onChange={(evento) => campo.onCambiar?.(evento.target.value)}
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: '#0F172A',
                        border: '1.5px solid #2563EB',
                        borderRadius: 7,
                        padding: '5px 9px',
                        outline: 'none',
                        background: '#F8FAFC',
                        width: '100%',
                        boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                    <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0 }}>{campo.valor}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Fila inferior */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Seguridad y Preferencias */}
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 14, padding: '22px 24px', boxShadow: '0 1px 4px rgba(15,23,42,0.04)' }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0F172A', marginBottom: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={15} color="#2563EB" strokeWidth={1.9} />
              Seguridad y Preferencias
            </h3>

            {!cambiandoContrasena ? (
              <button
                type="button"
                onClick={() => setCambiandoContrasena(true)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 14px',
                  background: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  borderRadius: 10,
                  cursor: 'pointer',
                  marginBottom: 10,
                  textAlign: 'left',
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(37,99,235,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Lock size={15} color="#2563EB" strokeWidth={1.9} />
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0 }}>Cambiar Contraseña</p>
                  <p style={{ fontSize: 11, color: '#94A3B8', margin: '2px 0 0' }}>Actualizada hace 14 días</p>
                </div>
                <ChevronRight size={15} color="#CBD5E1" />
              </button>
            ) : (
              <div style={{ background: '#F8FAFC', border: '1px solid #2563EB', borderRadius: 10, padding: '14px', marginBottom: 10 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#0F172A', marginBottom: 10 }}>Nueva contraseña</p>
                {['Nueva contraseña', 'Confirmar contraseña'].map((marcador) => (
                  <div key={marcador} style={{ position: 'relative', marginBottom: 8 }}>
                    <div style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', display: 'flex', pointerEvents: 'none' }}>
                      <Lock size={13} color="#94A3B8" strokeWidth={1.8} />
                    </div>
                    <input
                      type="password"
                      placeholder={marcador}
                      style={{
                        width: '100%',
                        boxSizing: 'border-box',
                        padding: '9px 12px 9px 32px',
                        fontSize: 13,
                        border: '1.5px solid #E2E8F0',
                        borderRadius: 7,
                        outline: 'none',
                        color: '#0F172A',
                        background: '#fff',
                      }}
                    />
                  </div>
                ))}
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button
                    type="button"
                    onClick={() => setCambiandoContrasena(false)}
                    style={{ flex: 1, background: '#2563EB', color: '#fff', border: 'none', borderRadius: 7, padding: '8px 0', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}
                  >
                    Guardar
                  </button>
                  <button
                    type="button"
                    onClick={() => setCambiandoContrasena(false)}
                    style={{ flex: 1, background: '#fff', color: '#64748B', border: '1px solid #E2E8F0', borderRadius: 7, padding: '8px 0', fontSize: 12, cursor: 'pointer' }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {!modificandoPalabraSecreta ? (
              <button
                type="button"
                onClick={() => setModificandoPalabraSecreta(true)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 14px',
                  background: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  borderRadius: 10,
                  cursor: 'pointer',
                  marginBottom: 10,
                  textAlign: 'left',
                }}
              >
                <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(37,99,235,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <KeyRound size={15} color="#2563EB" strokeWidth={1.9} />
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0 }}>Modificar Palabra Secreta</p>
                  <p style={{ fontSize: 11, color: '#94A3B8', margin: '2px 0 0' }}>Método alternativo de recuperación de acceso</p>
                </div>
                <ChevronRight size={15} color="#CBD5E1" />
              </button>
            ) : (
              <div style={{ background: '#F8FAFC', border: '1px solid #2563EB', borderRadius: 10, padding: '14px', marginBottom: 10 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#0F172A', marginBottom: 10 }}>Nueva palabra secreta</p>
                <div style={{ position: 'relative', marginBottom: 8 }}>
                  <div style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', display: 'flex', pointerEvents: 'none' }}>
                    <KeyRound size={13} color="#94A3B8" strokeWidth={1.8} />
                  </div>
                  <input
                    type="text"
                    placeholder="Nueva palabra o frase secreta"
                    value={palabraSecreta}
                    onChange={(evento) => setPalabraSecreta(evento.target.value)}
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '9px 12px 9px 32px',
                      fontSize: 13,
                      border: '1.5px solid #E2E8F0',
                      borderRadius: 7,
                      outline: 'none',
                      color: '#0F172A',
                      background: '#fff',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button
                    type="button"
                    onClick={() => setModificandoPalabraSecreta(false)}
                    style={{ flex: 1, background: '#2563EB', color: '#fff', border: 'none', borderRadius: 7, padding: '8px 0', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}
                  >
                    Guardar
                  </button>
                  <button
                    type="button"
                    onClick={() => setModificandoPalabraSecreta(false)}
                    style={{ flex: 1, background: '#fff', color: '#64748B', border: '1px solid #E2E8F0', borderRadius: 7, padding: '8px 0', fontSize: 12, cursor: 'pointer' }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: dosFactores ? 'rgba(22,163,74,0.1)' : 'rgba(220,38,38,0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Shield size={15} color={dosFactores ? '#16A34A' : '#DC2626'} strokeWidth={1.9} />
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0 }}>Autenticación de dos factores (2FA)</p>
                <p style={{ fontSize: 11, color: dosFactores ? '#16A34A' : '#DC2626', margin: '2px 0 0', fontWeight: 500 }}>
                  {dosFactores ? 'Activado — TOTP' : 'Desactivado'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDosFactores((valor) => !valor)}
                style={{
                  width: 36,
                  height: 20,
                  borderRadius: 10,
                  background: dosFactores ? '#16A34A' : '#E2E8F0',
                  border: 'none',
                  cursor: 'pointer',
                  position: 'relative',
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: 2,
                    left: dosFactores ? 18 : 2,
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    background: '#fff',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }}
                />
              </button>
            </div>
          </div>

          {/* Almacenamiento + actividad */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 14, padding: '20px 24px', boxShadow: '0 1px 4px rgba(15,23,42,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <Zap size={15} color="#2563EB" strokeWidth={1.9} />
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0F172A', margin: 0 }}>Plan Profesional</h3>
                <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 600, color: '#2563EB', background: 'rgba(37,99,235,0.08)', borderRadius: 20, padding: '2px 8px' }}>
                  $9/mes
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: '#64748B' }}>Almacenamiento usado</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#0F172A' }}>
                  {almacenamientoUsado} / {almacenamientoTotal} GB
                </span>
              </div>
              <div style={{ height: 7, background: '#F1F5F9', borderRadius: 4, overflow: 'hidden', marginBottom: 12 }}>
                <div style={{ width: `${(almacenamientoUsado / almacenamientoTotal) * 100}%`, height: '100%', background: '#2563EB', borderRadius: 4 }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                {CATEGORIAS_ALMACENAMIENTO.map((categoria) => (
                  <div key={categoria.etiqueta} style={{ background: '#F8FAFC', borderRadius: 7, padding: '8px 10px', borderLeft: `3px solid ${categoria.color}` }}>
                    <p style={{ fontSize: 11, color: '#64748B', margin: 0 }}>{categoria.etiqueta}</p>
                    <p style={{ fontSize: 12, fontWeight: 700, color: '#0F172A', margin: '2px 0 0' }}>{categoria.tamano}</p>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 14, padding: '18px 24px', boxShadow: '0 1px 4px rgba(15,23,42,0.04)' }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: '#0F172A', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 7 }}>
                <Activity size={14} color="#64748B" strokeWidth={1.9} />
                Actividad reciente
              </h3>
              {ACTIVIDAD_RECIENTE.map((evento) => (
                <div key={evento.archivo} style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 10, marginBottom: 10, borderBottom: '1px solid #F1F5F9' }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    {evento.icono}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 12, fontWeight: 500, color: '#0F172A', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {evento.archivo}
                    </p>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: '1px 0 0' }}>{evento.accion}</p>
                  </div>
                  <span style={{ fontSize: 11, color: '#94A3B8', flexShrink: 0 }}>{evento.tiempo}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

export default ProfilePage