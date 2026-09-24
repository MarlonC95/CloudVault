import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, Mail, Lock, Eye, EyeOff, Cloud } from 'lucide-react'
import { recuperarContrasena } from '../services/authService'

interface ErroresRecuperacion {
  correoElectronico?: string
  palabraSecreta?: string
  nuevaContrasena?: string
  confirmarNuevaContrasena?: string
}

const LONGITUD_MINIMA_CONTRASENA = 8
const COLOR_MARCA = '#2563EB'
const COLOR_NAVY = '#0F172A'
const COLOR_BORDE = '#E2E8F0'
const COLOR_FONDO = '#F8FAFC'

function RecoverPasswordPage() {
  const [correoElectronico, setCorreoElectronico] = useState('')
  const [palabraSecreta, setPalabraSecreta] = useState('')
  const [nuevaContrasena, setNuevaContrasena] = useState('')
  const [confirmarNuevaContrasena, setConfirmarNuevaContrasena] = useState('')
  const [mostrarContrasena, setMostrarContrasena] = useState(false)
  const [errores, setErrores] = useState<ErroresRecuperacion>({})
  const [estaEnviando, setEstaEnviando] = useState(false)
  const [errorGeneral, setErrorGeneral] = useState('')
  const [recuperacionExitosa, setRecuperacionExitosa] = useState(false)

  function validar(): ErroresRecuperacion {
    const erroresEncontrados: ErroresRecuperacion = {}
    const formatoCorreoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correoElectronico)

    if (!correoElectronico.trim()) {
      erroresEncontrados.correoElectronico = 'El correo es obligatorio'
    } else if (!formatoCorreoValido) {
      erroresEncontrados.correoElectronico = 'El formato del correo no es válido'
    }

    if (!palabraSecreta.trim()) {
      erroresEncontrados.palabraSecreta = 'Ingresa tu palabra secreta'
    }

    if (!nuevaContrasena) {
      erroresEncontrados.nuevaContrasena = 'La nueva contraseña es obligatoria'
    } else if (nuevaContrasena.length < LONGITUD_MINIMA_CONTRASENA) {
      erroresEncontrados.nuevaContrasena = `Debe tener al menos ${LONGITUD_MINIMA_CONTRASENA} caracteres`
    }

    if (!confirmarNuevaContrasena) {
      erroresEncontrados.confirmarNuevaContrasena = 'Confirma tu nueva contraseña'
    } else if (confirmarNuevaContrasena !== nuevaContrasena) {
      erroresEncontrados.confirmarNuevaContrasena = 'Las contraseñas no coinciden'
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
      await recuperarContrasena({ correoElectronico, palabraSecreta, nuevaContrasena })
      setRecuperacionExitosa(true)
    } catch (error) {
      setErrorGeneral('El correo o la palabra secreta no coinciden con ningún registro.')
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
        style={{ maxWidth: '440px', borderRadius: '12px' }}
      >
        <div className="d-flex align-items-center gap-3 mb-3">
          <div
            className="d-flex justify-content-center align-items-center flex-shrink-0"
            style={{ width: '48px', height: '48px', backgroundColor: COLOR_NAVY, borderRadius: '10px' }}
          >
            <Cloud size={24} color={COLOR_MARCA} />
          </div>
          <div>
            <h2 className="fw-bold mb-0 fs-4">Recuperar contraseña</h2>
            <p className="text-secondary small mb-0">Verifica tu identidad con tu palabra secreta.</p>
          </div>
        </div>

        <hr className="mb-4" />

        {recuperacionExitosa ? (
          <div className="text-center py-3">
            <div className="alert alert-success">
              Tu contraseña fue actualizada correctamente.
            </div>
            <Link to="/login" className="btn w-100 text-white fw-semibold" style={{ backgroundColor: COLOR_MARCA }}>
              Ir a Iniciar Sesión
            </Link>
          </div>
        ) : (
          <>
            {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

            <form onSubmit={manejarEnvio} noValidate>
              <div className="mb-3">
                <label htmlFor="correoElectronico" className="form-label">
                  Correo electrónico
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
                <label htmlFor="palabraSecreta" className="form-label">
                  Palabra / Frase Secreta
                </label>
                <div className="input-group has-validation">
                  <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                    <KeyRound size={18} className="text-secondary" />
                  </span>
                  <input
                    id="palabraSecreta"
                    type="text"
                    className={`form-control ${errores.palabraSecreta ? 'is-invalid' : ''}`}
                    style={{ borderColor: COLOR_BORDE }}
                    placeholder="La que ingresaste al registrarte"
                    value={palabraSecreta}
                    onChange={(evento) => setPalabraSecreta(evento.target.value)}
                    disabled={estaEnviando}
                  />
                  {errores.palabraSecreta && (
                    <div className="invalid-feedback">{errores.palabraSecreta}</div>
                  )}
                </div>
              </div>

              <div className="mb-3">
                <label htmlFor="nuevaContrasena" className="form-label">
                  Nueva contraseña
                </label>
                <div className="input-group has-validation">
                  <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                    <Lock size={18} className="text-secondary" />
                  </span>
                  <input
                    id="nuevaContrasena"
                    type={mostrarContrasena ? 'text' : 'password'}
                    className={`form-control ${errores.nuevaContrasena ? 'is-invalid' : ''}`}
                    style={{ borderColor: COLOR_BORDE }}
                    placeholder={`Mínimo ${LONGITUD_MINIMA_CONTRASENA} caracteres`}
                    value={nuevaContrasena}
                    onChange={(evento) => setNuevaContrasena(evento.target.value)}
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
                  {errores.nuevaContrasena && (
                    <div className="invalid-feedback">{errores.nuevaContrasena}</div>
                  )}
                </div>
              </div>

              <div className="mb-4">
                <label htmlFor="confirmarNuevaContrasena" className="form-label">
                  Confirmar nueva contraseña
                </label>
                <div className="input-group has-validation">
                  <span className="input-group-text bg-white" style={{ borderColor: COLOR_BORDE }}>
                    <Lock size={18} className="text-secondary" />
                  </span>
                  <input
                    id="confirmarNuevaContrasena"
                    type={mostrarContrasena ? 'text' : 'password'}
                    className={`form-control ${errores.confirmarNuevaContrasena ? 'is-invalid' : ''}`}
                    style={{ borderColor: COLOR_BORDE }}
                    placeholder="Repite tu nueva contraseña"
                    value={confirmarNuevaContrasena}
                    onChange={(evento) => setConfirmarNuevaContrasena(evento.target.value)}
                    disabled={estaEnviando}
                  />
                  {errores.confirmarNuevaContrasena && (
                    <div className="invalid-feedback">{errores.confirmarNuevaContrasena}</div>
                  )}
                </div>
              </div>

              <button
                type="submit"
                className="btn w-100 text-white fw-semibold"
                style={{ backgroundColor: COLOR_MARCA }}
                disabled={estaEnviando}
              >
                {estaEnviando ? 'Verificando...' : 'Restablecer contraseña'}
              </button>
            </form>
          </>
        )}

        <p className="text-center mt-4 small text-secondary mb-0">
          <Link to="/login" className="text-decoration-none" style={{ color: COLOR_MARCA }}>
            Volver a Iniciar Sesión
          </Link>
        </p>
      </div>
    </div>
  )
}

export default RecoverPasswordPage