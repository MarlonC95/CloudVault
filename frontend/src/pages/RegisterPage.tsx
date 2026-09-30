import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Mail, Lock, KeyRound, Eye, EyeOff, Cloud } from 'lucide-react'
import { ErrorRegistro, registrarUsuario } from '../services/authService'

interface ErroresRegistro {
  nombreCompleto?: string
  correoElectronico?: string
  contrasena?: string
  confirmarContrasena?: string
  palabraSecreta?: string
  aceptaTerminos?: string
}

const LONGITUD_MINIMA_CONTRASENA = 8
const LONGITUD_MAXIMA_CONTRASENA = 128
const LONGITUD_MINIMA_PALABRA_SECRETA = 12
const LONGITUD_MAXIMA_PALABRA_SECRETA = 128
const COLOR_MARCA = '#2563EB'
const COLOR_NAVY = '#0F172A'
const COLOR_ICONO_FONDO = '#EFF4FF'
const COLOR_FONDO_PAGINA = '#F1F5F9'

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
  const navegar = useNavigate()

  function validar(): ErroresRegistro {
    const erroresEncontrados: ErroresRegistro = {}
    const correoNormalizado = correoElectronico.trim()
    const formatoCorreoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correoNormalizado)

    if (!nombreCompleto.trim()) {
      erroresEncontrados.nombreCompleto = 'El nombre es obligatorio'
    } else if (Array.from(nombreCompleto.trim()).length > 150) {
      erroresEncontrados.nombreCompleto = 'El nombre no puede superar 150 caracteres'
    }

    if (!correoElectronico.trim()) {
      erroresEncontrados.correoElectronico = 'El correo es obligatorio'
    } else if (Array.from(correoNormalizado).length > 255) {
      erroresEncontrados.correoElectronico = 'El correo no puede superar 255 caracteres'
    } else if (!formatoCorreoValido) {
      erroresEncontrados.correoElectronico = 'El formato del correo no es válido'
    }

    if (!contrasena) {
      erroresEncontrados.contrasena = 'La contraseña es obligatoria'
    } else if (Array.from(contrasena).length < LONGITUD_MINIMA_CONTRASENA) {
      erroresEncontrados.contrasena = `Debe tener al menos ${LONGITUD_MINIMA_CONTRASENA} caracteres`
    } else if (Array.from(contrasena).length > LONGITUD_MAXIMA_CONTRASENA) {
      erroresEncontrados.contrasena = `No puede superar ${LONGITUD_MAXIMA_CONTRASENA} caracteres`
    }

    if (!confirmarContrasena) {
      erroresEncontrados.confirmarContrasena = 'Confirma tu contraseña'
    } else if (confirmarContrasena !== contrasena) {
      erroresEncontrados.confirmarContrasena = 'Las contraseñas no coinciden'
    }

    if (!palabraSecreta.trim()) {
      erroresEncontrados.palabraSecreta = 'La palabra secreta es obligatoria'
    } else if (Array.from(palabraSecreta).length < LONGITUD_MINIMA_PALABRA_SECRETA) {
      erroresEncontrados.palabraSecreta = `Debe tener al menos ${LONGITUD_MINIMA_PALABRA_SECRETA} caracteres`
    } else if (Array.from(palabraSecreta).length > LONGITUD_MAXIMA_PALABRA_SECRETA) {
      erroresEncontrados.palabraSecreta = `No puede superar ${LONGITUD_MAXIMA_PALABRA_SECRETA} caracteres`
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
      navegar('/login', { state: { registroExitoso: true } })
    } catch (error) {
      if (error instanceof ErrorRegistro) {
        const campos = error.campos
        setErrores({
          nombreCompleto: campos.nombre_completo?.[0],
          correoElectronico: campos.correo_electronico?.[0],
          contrasena: campos.contrasena?.[0],
          palabraSecreta: campos.palabra_secreta?.[0],
        })
        setErrorGeneral(campos.non_field_errors?.[0] ?? error.message)
      } else {
        setErrorGeneral('Ocurrió un error al registrar tu cuenta. Intenta de nuevo.')
      }
    } finally {
      setEstaEnviando(false)
    }
  }

  return (
    <div
  className="d-flex justify-content-center align-items-start align-items-md-center min-vh-100 py-5 px-3"
  style={{ backgroundColor: COLOR_FONDO_PAGINA }}
    >
      <div
        className="bg-white shadow-lg overflow-hidden w-100"
        style={{ maxWidth: '760px', borderRadius: '28px' }}
      >
        {/* Franja curva de branding */}
        <div
          className="d-flex flex-column justify-content-center align-items-center text-white text-center py-4"
          style={{
            backgroundColor: COLOR_NAVY,
            borderRadius: '0 0 50% 50% / 0 0 50px 20px',
          }}
        >
          <Cloud size={36} strokeWidth={1.5} className="mb-1" />
          <span className="fw-bold">CloudVault</span>
        </div>

        <div className="p-4 p-md-5 px-md-4 px-lg-5 pt-4">
          <h2 className="fw-bold mb-1 fs-4">Crear cuenta</h2>
          <p className="text-secondary small mb-4">Comienza a gestionar tu infraestructura PaaS.</p>

          {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

          <form onSubmit={manejarEnvio} noValidate>
            <div className="row g-3 mb-3">
              <div className="col-12 col-sm-6">
                <label htmlFor="nombreCompleto" className="form-label small fw-semibold">
                  Nombre completo
                </label>
                <div className="input-group has-validation">
                  <span
                    className="input-group-text border-0"
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                  >
                    <User size={18} color={COLOR_MARCA} />
                  </span>
                  <input
                    id="nombreCompleto"
                    type="text"
                    className={`form-control border-0 ${errores.nombreCompleto ? 'is-invalid' : ''}`}
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
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

              <div className="col-12 col-sm-6">
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
            </div>

            <div className="row g-3 mb-3">
              <div className="col-12 col-sm-6">
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
                    placeholder={`Mínimo ${LONGITUD_MINIMA_CONTRASENA} caracteres`}
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

              <div className="col-12 col-sm-6">
                <label htmlFor="confirmarContrasena" className="form-label small fw-semibold">
                  Confirmar contraseña
                </label>
                <div className="input-group has-validation">
                  <span
                    className="input-group-text border-0"
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                  >
                    <Lock size={18} color={COLOR_MARCA} />
                  </span>
                  <input
                    id="confirmarContrasena"
                    type={mostrarContrasena ? 'text' : 'password'}
                    className={`form-control border-0 ${errores.confirmarContrasena ? 'is-invalid' : ''}`}
                    style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
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
            </div>

            <div className="mb-3">
              <label htmlFor="palabraSecreta" className="form-label small fw-semibold">
                Palabra / Frase Secreta de Recuperación
              </label>
              <div className="input-group has-validation">
                <span
                  className="input-group-text border-0"
                  style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                >
                  <KeyRound size={18} color={COLOR_MARCA} />
                </span>
                <input
                  id="palabraSecreta"
                  type={mostrarPalabraSecreta ? 'text' : 'password'}
                  className={`form-control border-0 ${errores.palabraSecreta ? 'is-invalid' : ''}`}
                  style={{ backgroundColor: COLOR_ICONO_FONDO }}
                  placeholder="Ingresa tu palabra o frase secreta"
                  value={palabraSecreta}
                  onChange={(evento) => setPalabraSecreta(evento.target.value)}
                  disabled={estaEnviando}
                />
                <button
                  type="button"
                  className="btn border-0"
                  style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
                  onClick={() => setMostrarPalabraSecreta(!mostrarPalabraSecreta)}
                  disabled={estaEnviando}
                  aria-label={mostrarPalabraSecreta ? 'Ocultar palabra secreta' : 'Mostrar palabra secreta'}
                >
                  {mostrarPalabraSecreta ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
                {errores.palabraSecreta && (
                  <div className="invalid-feedback">{errores.palabraSecreta}</div>
                )}
              </div>
              {!errores.palabraSecreta && (
                <div className="form-text px-2">
                  La usarás si olvidas tu contraseña. Guárdala en un lugar seguro.
                </div>
              )}
            </div>

            <div className="mb-4 px-2">
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
              className="btn w-100 text-white fw-semibold py-2"
              style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px' }}
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
    </div>
  )
}

export default RegisterPage
