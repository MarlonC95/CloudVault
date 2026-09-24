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
const COLOR_BORDE = '#E2E8F0'

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
    <div className="d-flex min-vh-100">
      {/* Panel izquierdo: solo visible en pantallas medianas en adelante */}
      <div
        className="d-none d-md-flex flex-column justify-content-center align-items-center text-white"
        style={{ width: '45%', backgroundColor: COLOR_NAVY }}
      >
        <Cloud size={64} color={COLOR_MARCA} strokeWidth={1.5} />
        <h2 className="mt-3 fw-bold">CloudVault</h2>
      </div>

      {/* Panel derecho: formulario, siempre visible */}
      <div className="d-flex flex-column justify-content-center flex-grow-1 px-4 px-md-5 bg-white">
        <div className="mx-auto w-100" style={{ maxWidth: '400px' }}>
          <h2 className="fw-bold mb-4">Iniciar Sesión</h2>

          {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

          <form onSubmit={manejarEnvio} noValidate>
            <div className="mb-3">
              <label htmlFor="correoElectronico" className="form-label">
                Correo corporativo
              </label>
              <div className="input-group has-validation">
                <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                  <Mail size={18} className="text-secondary" />
                </span>
                <input
                  id="correoElectronico"
                  type="email"
                  className={`form-control ${errores.correoElectronico ? 'is-invalid' : ''}`}
                  style={{ borderColor: COLOR_BORDE }}
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

            <div className="mb-3">
              <label htmlFor="contrasena" className="form-label">
                Contraseña
              </label>
              <div className="input-group has-validation">
                <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                  <Lock size={18} className="text-secondary" />
                </span>
                <input
                  id="contrasena"
                  type={mostrarContrasena ? 'text' : 'password'}
                  className={`form-control ${errores.contrasena ? 'is-invalid' : ''}`}
                  style={{ borderColor: COLOR_BORDE }}
                  placeholder="Tu contraseña"
                  value={contrasena}
                  onChange={(evento) => setContrasena(evento.target.value)}
                  disabled={estaEnviando}
                />
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  style={{ borderColor: COLOR_BORDE }}
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

            <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="recordarSesion" />
                <label className="form-check-label small" htmlFor="recordarSesion">
                  Recordar sesión
                </label>
              </div>
              <Link to="/recuperar" className="small text-decoration-none" style={{ color: COLOR_MARCA }}>
                ¿Olvidaste tu contraseña?
              </Link>
            </div>

            <button
              type="submit"
              className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold"
              style={{ backgroundColor: COLOR_MARCA }}
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
              Regístrate gratis
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage