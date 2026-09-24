import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Cloud, Mail, Lock, Eye, EyeOff, ChevronRight } from 'lucide-react'
import { iniciarSesion } from '../services/authService'

interface ErroresLogin {
  correoElectronico?: string
  contrasena?: string
}

const COLOR_MARCA = '#2563EB'
const COLOR_NAVY = '#0F172A'
const COLOR_ICONO_FONDO = '#EFF4FF'
const COLOR_FONDO_PAGINA = '#F1F5F9'

function LoginPage() {
  const [correoElectronico, setCorreoElectronico] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [mostrarContrasena, setMostrarContrasena] = useState(false)
  const [errores, setErrores] = useState<ErroresLogin>({})
  const [estaEnviando, setEstaEnviando] = useState(false)
  const [errorGeneral, setErrorGeneral] = useState('')

  function validar(): ErroresLogin {
    const erroresEncontrados: ErroresLogin = {}
    const formatoCorreoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correoElectronico)

    if (!correoElectronico.trim()) {
      erroresEncontrados.correoElectronico = 'El correo es obligatorio'
    } else if (!formatoCorreoValido) {
      erroresEncontrados.correoElectronico = 'El formato del correo no es válido'
    }

    if (!contrasena) {
      erroresEncontrados.contrasena = 'La contraseña es obligatoria'
    }

    return erroresEncontrados
  }

  async function manejarEnvio(evento: React.FormEvent) {
    evento.preventDefault()
    const erroresEncontrados = validar()
    setErrores(erroresEncontrados)

    if (Object.keys(erroresEncontrados).length > 0) return

    setEstaEnviando(true)
    setErrorGeneral('')

    try {
      const respuesta = await iniciarSesion({ correoElectronico, contrasena })
      console.log('Login exitoso:', respuesta)
      // TODO: guardar el token (AuthContext) y redirigir al dashboard
    } catch (error) {
      setErrorGeneral('Correo o contraseña incorrectos.')
    } finally {
      setEstaEnviando(false)
    }
  }

  return (
   <div
  className="d-flex justify-content-center align-items-center min-vh-100 px-3 py-4"
  style={{ backgroundColor: COLOR_FONDO_PAGINA }}
  >
      <div
        className="d-flex bg-white shadow-lg overflow-hidden"
        style={{ borderRadius: '28px', maxWidth: '900px', width: '100%' }}
      >
        {/* Columna del formulario */}
        <div className="p-4 p-md-5 flex-grow-1" style={{ minWidth: 0 }}>
          <div className="mx-auto w-100" style={{ maxWidth: '360px' }}>
            <h2 className="fw-bold mb-1">¡Hola de nuevo!</h2>
            <p className="text-secondary mb-4">Inicia sesión en tu cuenta</p>

            {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

            <form onSubmit={manejarEnvio} noValidate>
              <div className="mb-3">
                <label htmlFor="correoElectronico" className="form-label small fw-semibold">
                  Correo electrónico
                </label>
                <div className="input-group has-validation">
                  <span
                    className="input-group-text border-0"
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                  >
                    <Mail size={18} color={COLOR_MARCA} />
                  </span>
                  <input
                    id="correoElectronico"
                    type="email"
                    className={`form-control border-0 ${errores.correoElectronico ? 'is-invalid' : ''}`}
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
                    placeholder="nombre@empresa.com"
                    value={correoElectronico}
                    onChange={(evento) => setCorreoElectronico(evento.target.value)}
                    disabled={estaEnviando}
                  />
                  {errores.correoElectronico && (
                    <div className="invalid-feedback">{errores.correoElectronico}</div>
                  )}
                </div>
              </div>

              <div className="mb-2">
                <label htmlFor="contrasena" className="form-label small fw-semibold">
                  Contraseña
                </label>
                <div className="input-group has-validation">
                  <span
                    className="input-group-text border-0"
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                  >
                    <Lock size={18} color={COLOR_MARCA} />
                  </span>
                  <input
                    id="contrasena"
                    type={mostrarContrasena ? 'text' : 'password'}
                    className={`form-control border-0 ${errores.contrasena ? 'is-invalid' : ''}`}
                    style={{ backgroundColor: COLOR_ICONO_FONDO }}
                    placeholder="Tu contraseña"
                    value={contrasena}
                    onChange={(evento) => setContrasena(evento.target.value)}
                    disabled={estaEnviando}
                  />
                  <button
                    type="button"
                    className="btn border-0"
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
                    onClick={() => setMostrarContrasena(!mostrarContrasena)}
                    disabled={estaEnviando}
                    aria-label={mostrarContrasena ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  >
                    {mostrarContrasena ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                  {errores.contrasena && (
                    <div className="invalid-feedback">{errores.contrasena}</div>
                  )}
                </div>
              </div>

              <div className="d-flex justify-content-between align-items-center mb-4 mt-2 flex-wrap gap-2 px-2">
                <div className="form-check">
                  <input className="form-check-input" type="checkbox" id="recordarSesion" />
                  <label className="form-check-label small" htmlFor="recordarSesion">
                    Recordarme
                  </label>
                </div>
                <Link to="/recuperar" className="small text-decoration-none" style={{ color: COLOR_MARCA }}>
                  ¿Olvidaste tu contraseña?
                </Link>
              </div>

              <button
                type="submit"
                className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold py-2"
                style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px' }}
                disabled={estaEnviando}
              >
                {estaEnviando ? (
                  'Entrando...'
                ) : (
                  <>
                    Iniciar Sesión <ChevronRight size={18} />
                  </>
                )}
              </button>
            </form>

            <p className="text-center mt-4 small text-secondary">
              ¿No tienes cuenta?{' '}
              <Link to="/registro" className="fw-semibold text-decoration-none" style={{ color: COLOR_MARCA }}>
                Crear cuenta
              </Link>
            </p>
          </div>
        </div>

        {/* Columna de branding con borde de ola: solo visible desde md en adelante */}
        <div
          className="d-none d-md-flex flex-column justify-content-center align-items-center text-white text-center p-5"
          style={{
            width: '380px',
            backgroundColor: COLOR_NAVY,
            flexShrink: 0,
            borderRadius: '18% 0 0 18% / 22% 0 0 14%',
          }}
        >
          <Cloud size={56} strokeWidth={1.5} className="mb-3" />
          <h3 className="fw-bold mb-2">CloudVault</h3>
          <p className="small opacity-75 mb-0">
            Tu almacenamiento, organizado y seguro en un solo lugar.
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage