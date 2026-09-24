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
const COLOR_ICONO_FONDO = '#EFF4FF'

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
    <div className="d-flex justify-content-center align-items-start align-items-md-center min-vh-100 py-5 px-3 bg-light">
      <div
        className="bg-white shadow-lg overflow-hidden w-100"
        style={{ maxWidth: '440px', borderRadius: '28px' }}
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

        <div className="p-4 p-md-5 pt-4">
          <h2 className="fw-bold mb-1 fs-4">Recuperar contraseña</h2>
          <p className="text-secondary small mb-4">Verifica tu identidad con tu palabra secreta.</p>

          {recuperacionExitosa ? (
            <div className="text-center py-3">
              <div className="alert alert-success">
                Tu contraseña fue actualizada correctamente.
              </div>
              <Link
                to="/login"
                className="btn w-100 text-white fw-semibold py-2"
                style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px' }}
              >
                Ir a Iniciar Sesión
              </Link>
            </div>
          ) : (
            <>
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

                <div className="mb-3">
                  <label htmlFor="palabraSecreta" className="form-label small fw-semibold">
                    Palabra / Frase Secreta
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
                      type="text"
                      className={`form-control border-0 ${errores.palabraSecreta ? 'is-invalid' : ''}`}
                      style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
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
                  <label htmlFor="nuevaContrasena" className="form-label small fw-semibold">
                    Nueva contraseña
                  </label>
                  <div className="input-group has-validation">
                    <span
                      className="input-group-text border-0"
                      style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                    >
                      <Lock size={18} color={COLOR_MARCA} />
                    </span>
                    <input
                      id="nuevaContrasena"
                      type={mostrarContrasena ? 'text' : 'password'}
                      className={`form-control border-0 ${errores.nuevaContrasena ? 'is-invalid' : ''}`}
                      style={{ backgroundColor: COLOR_ICONO_FONDO }}
                      placeholder={`Mínimo ${LONGITUD_MINIMA_CONTRASENA} caracteres`}
                      value={nuevaContrasena}
                      onChange={(evento) => setNuevaContrasena(evento.target.value)}
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
                    {errores.nuevaContrasena && (
                      <div className="invalid-feedback">{errores.nuevaContrasena}</div>
                    )}
                  </div>
                </div>

                <div className="mb-4">
                  <label htmlFor="confirmarNuevaContrasena" className="form-label small fw-semibold">
                    Confirmar nueva contraseña
                  </label>
                  <div className="input-group has-validation">
                    <span
                      className="input-group-text border-0"
                      style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '50px 0 0 50px' }}
                    >
                      <Lock size={18} color={COLOR_MARCA} />
                    </span>
                    <input
                      id="confirmarNuevaContrasena"
                      type={mostrarContrasena ? 'text' : 'password'}
                      className={`form-control border-0 ${errores.confirmarNuevaContrasena ? 'is-invalid' : ''}`}
                      style={{ backgroundColor: COLOR_ICONO_FONDO, borderRadius: '0 50px 50px 0' }}
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
                  className="btn w-100 text-white fw-semibold py-2"
                  style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px' }}
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
    </div>
  )
}

export default RecoverPasswordPage