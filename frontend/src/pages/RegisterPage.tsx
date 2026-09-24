import { useState } from 'react'
import { Link } from 'react-router-dom'
import { User, Mail, Lock, KeyRound, Eye, EyeOff, Cloud } from 'lucide-react'
import { registrarUsuario } from '../services/authService'

interface ErroresRegistro {
  nombreCompleto?: string
  correoElectronico?: string
  contrasena?: string
  confirmarContrasena?: string
  palabraSecreta?: string
  aceptaTerminos?: string
}

const LONGITUD_MINIMA_CONTRASENA = 8
const COLOR_MARCA = '#2563EB'
const COLOR_NAVY = '#0F172A'
const COLOR_BORDE = '#E2E8F0'
const COLOR_FONDO = '#F8FAFC'

function RegisterPage() {
  const [nombreCompleto, setNombreCompleto] = useState('')
  const [correoElectronico, setCorreoElectronico] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [confirmarContrasena, setConfirmarContrasena] = useState('')
  const [palabraSecreta, setPalabraSecreta] = useState('')
  const [aceptaTerminos, setAceptaTerminos] = useState(false)
  const [mostrarContrasena, setMostrarContrasena] = useState(false)
  const [mostrarPalabraSecreta, setMostrarPalabraSecreta] = useState(false)
  const [errores, setErrores] = useState<ErroresRegistro>({})
  const [estaEnviando, setEstaEnviando] = useState(false)
  const [errorGeneral, setErrorGeneral] = useState('')

  function validar(): ErroresRegistro {
    const erroresEncontrados: ErroresRegistro = {}
    const formatoCorreoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correoElectronico)

    if (!nombreCompleto.trim()) {
      erroresEncontrados.nombreCompleto = 'El nombre es obligatorio'
    }

    if (!correoElectronico.trim()) {
      erroresEncontrados.correoElectronico = 'El correo es obligatorio'
    } else if (!formatoCorreoValido) {
      erroresEncontrados.correoElectronico = 'El formato del correo no es válido'
    }

    if (!contrasena) {
      erroresEncontrados.contrasena = 'La contraseña es obligatoria'
    } else if (contrasena.length < LONGITUD_MINIMA_CONTRASENA) {
      erroresEncontrados.contrasena = `Debe tener al menos ${LONGITUD_MINIMA_CONTRASENA} caracteres`
    }

    if (!confirmarContrasena) {
      erroresEncontrados.confirmarContrasena = 'Confirma tu contraseña'
    } else if (confirmarContrasena !== contrasena) {
      erroresEncontrados.confirmarContrasena = 'Las contraseñas no coinciden'
    }

    if (!palabraSecreta.trim()) {
      erroresEncontrados.palabraSecreta = 'La palabra secreta es obligatoria'
    }

    if (!aceptaTerminos) {
      erroresEncontrados.aceptaTerminos = 'Debes aceptar los términos para continuar'
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
      await registrarUsuario({ nombreCompleto, correoElectronico, contrasena, palabraSecreta })
      console.log('Registro exitoso')
      // TODO: redirigir al login o al dashboard cuando exista esa pantalla
    } catch (error) {
      setErrorGeneral('Ocurrió un error al registrar tu cuenta. Intenta de nuevo.')
    } finally {
      setEstaEnviando(false)
    }
  }

  return (
    <div
      className="d-flex justify-content-center align-items-start align-items-md-center min-vh-100 py-5 px-3"
      style={{ backgroundColor: COLOR_FONDO }}
    >
      <div
        className="card border-0 shadow-sm p-4 p-md-5 w-100"
        style={{ maxWidth: '480px', borderRadius: '12px' }}
      >
        <div className="d-flex align-items-center gap-3 mb-3">
          <div
            className="d-flex justify-content-center align-items-center flex-shrink-0"
            style={{ width: '48px', height: '48px', backgroundColor: COLOR_NAVY, borderRadius: '10px' }}
          >
            <Cloud size={24} color={COLOR_MARCA} />
          </div>
          <div>
            <h2 className="fw-bold mb-0 fs-4">Crear cuenta en CloudVault</h2>
            <p className="text-secondary small mb-0">Comienza a gestionar tu infraestructura PaaS.</p>
          </div>
        </div>

        <hr className="mb-4" />

        {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

        <form onSubmit={manejarEnvio} noValidate>
          <div className="mb-3">
            <label htmlFor="nombreCompleto" className="form-label">
              Nombre Completo
            </label>
            <div className="input-group has-validation">
              <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                <User size={18} className="text-secondary" />
              </span>
              <input
                id="nombreCompleto"
                type="text"
                className={`form-control ${errores.nombreCompleto ? 'is-invalid' : ''}`}
                style={{ borderColor: COLOR_BORDE }}
                placeholder="Mily Santay"
                value={nombreCompleto}
                onChange={(evento) => setNombreCompleto(evento.target.value)}
                disabled={estaEnviando}
              />
              {errores.nombreCompleto && (
                <div className="invalid-feedback">{errores.nombreCompleto}</div>
              )}
            </div>
          </div>

          <div className="mb-3">
            <label htmlFor="correoElectronico" className="form-label">
              Correo Electrónico
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
                placeholder={`Mínimo ${LONGITUD_MINIMA_CONTRASENA} caracteres`}
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

          <div className="mb-3">
            <label htmlFor="confirmarContrasena" className="form-label">
              Confirmar Contraseña
            </label>
            <div className="input-group has-validation">
              <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                <Lock size={18} className="text-secondary" />
              </span>
              <input
                id="confirmarContrasena"
                type={mostrarContrasena ? 'text' : 'password'}
                className={`form-control ${errores.confirmarContrasena ? 'is-invalid' : ''}`}
                style={{ borderColor: COLOR_BORDE }}
                placeholder="Repite tu contraseña"
                value={confirmarContrasena}
                onChange={(evento) => setConfirmarContrasena(evento.target.value)}
                disabled={estaEnviando}
              />
              {errores.confirmarContrasena && (
                <div className="invalid-feedback">{errores.confirmarContrasena}</div>
              )}
            </div>
          </div>

          <div className="mb-3">
            <label htmlFor="palabraSecreta" className="form-label">
              Palabra / Frase Secreta de Recuperación
            </label>
            <div className="input-group has-validation">
              <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                <KeyRound size={18} className="text-secondary" />
              </span>
              <input
                id="palabraSecreta"
                type={mostrarPalabraSecreta ? 'text' : 'password'}
                className={`form-control ${errores.palabraSecreta ? 'is-invalid' : ''}`}
                style={{ borderColor: COLOR_BORDE }}
                placeholder="Ingresa tu palabra o frase secreta"
                value={palabraSecreta}
                onChange={(evento) => setPalabraSecreta(evento.target.value)}
                disabled={estaEnviando}
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                style={{ borderColor: COLOR_BORDE }}
                onClick={() => setMostrarPalabraSecreta(!mostrarPalabraSecreta)}
                disabled={estaEnviando}
                aria-label={mostrarPalabraSecreta ? 'Ocultar palabra secreta' : 'Mostrar palabra secreta'}
              >
                {mostrarPalabraSecreta ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
              {errores.palabraSecreta ? (
                <div className="invalid-feedback">{errores.palabraSecreta}</div>
              ) : (
                <div className="form-text">
                  La usarás si olvidas tu contraseña. Guárdala en un lugar seguro.
                </div>
              )}
            </div>
          </div>

          <div className="mb-4">
            <div className="form-check">
              <input
                className={`form-check-input ${errores.aceptaTerminos ? 'is-invalid' : ''}`}
                type="checkbox"
                id="aceptaTerminos"
                checked={aceptaTerminos}
                onChange={(evento) => setAceptaTerminos(evento.target.checked)}
                disabled={estaEnviando}
              />
              <label className="form-check-label small" htmlFor="aceptaTerminos">
                Acepto los{' '}
                <a href="#" className="text-decoration-none" style={{ color: COLOR_MARCA }}>
                  términos del servicio
                </a>{' '}
                y{' '}
                <a href="#" className="text-decoration-none" style={{ color: COLOR_MARCA }}>
                  políticas de privacidad
                </a>
                .
              </label>
              {errores.aceptaTerminos && (
                <div className="invalid-feedback d-block">{errores.aceptaTerminos}</div>
              )}
            </div>
          </div>

          <button
            type="submit"
            className="btn w-100 text-white fw-semibold"
            style={{ backgroundColor: COLOR_MARCA }}
            disabled={estaEnviando}
          >
            {estaEnviando ? 'Registrando...' : 'Crear Cuenta'}
          </button>
        </form>

        <p className="text-center mt-4 small text-secondary mb-0">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="fw-semibold text-decoration-none" style={{ color: COLOR_MARCA }}>
            Iniciar Sesión
          </Link>
        </p>
      </div>
    </div>
  )
}

export default RegisterPage