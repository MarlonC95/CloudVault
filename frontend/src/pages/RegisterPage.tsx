import { useState } from 'react'
import { registrarUsuario } from '../services/authService'

interface ErroresRegistro {
  nombreCompleto?: string
  correoElectronico?: string
  contrasena?: string
  confirmarContrasena?: string
  palabraSecreta?: string
}

const LONGITUD_MINIMA_CONTRASENA = 8

function RegisterPage() {
  const [nombreCompleto, setNombreCompleto] = useState('')
  const [correoElectronico, setCorreoElectronico] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [confirmarContrasena, setConfirmarContrasena] = useState('')
  const [palabraSecreta, setPalabraSecreta] = useState('')
  const [mostrarContrasena, setMostrarContrasena] = useState(false)
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
    <div className="d-flex justify-content-center align-items-center min-vh-100 bg-light py-4">
      <div className="card p-4 shadow-sm" style={{ width: '400px' }}>
        <h2 className="mb-4 text-center">Crear cuenta</h2>

        {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

        <form onSubmit={manejarEnvio} noValidate>
          <div className="mb-3">
            <label htmlFor="nombreCompleto" className="form-label">
              Nombre completo
            </label>
            <input
              id="nombreCompleto"
              type="text"
              className={`form-control ${errores.nombreCompleto ? 'is-invalid' : ''}`}
              value={nombreCompleto}
              onChange={(evento) => setNombreCompleto(evento.target.value)}
              disabled={estaEnviando}
            />
            {errores.nombreCompleto && (
              <div className="invalid-feedback">{errores.nombreCompleto}</div>
            )}
          </div>

          <div className="mb-3">
            <label htmlFor="correoElectronico" className="form-label">
              Correo electrónico
            </label>
            <input
              id="correoElectronico"
              type="email"
              className={`form-control ${errores.correoElectronico ? 'is-invalid' : ''}`}
              value={correoElectronico}
              onChange={(evento) => setCorreoElectronico(evento.target.value)}
              disabled={estaEnviando}
            />
            {errores.correoElectronico && (
              <div className="invalid-feedback">{errores.correoElectronico}</div>
            )}
          </div>

          <div className="mb-3">
            <label htmlFor="contrasena" className="form-label">
              Contraseña
            </label>
            <div className="input-group has-validation">
              <input
                id="contrasena"
                type={mostrarContrasena ? 'text' : 'password'}
                className={`form-control ${errores.contrasena ? 'is-invalid' : ''}`}
                value={contrasena}
                onChange={(evento) => setContrasena(evento.target.value)}
                disabled={estaEnviando}
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setMostrarContrasena(!mostrarContrasena)}
                disabled={estaEnviando}
              >
                {mostrarContrasena ? 'Ocultar' : 'Ver'}
              </button>
              {errores.contrasena && (
                <div className="invalid-feedback">{errores.contrasena}</div>
              )}
            </div>
          </div>

          <div className="mb-3">
            <label htmlFor="confirmarContrasena" className="form-label">
              Confirmar contraseña
            </label>
            <input
              id="confirmarContrasena"
              type={mostrarContrasena ? 'text' : 'password'}
              className={`form-control ${errores.confirmarContrasena ? 'is-invalid' : ''}`}
              value={confirmarContrasena}
              onChange={(evento) => setConfirmarContrasena(evento.target.value)}
              disabled={estaEnviando}
            />
            {errores.confirmarContrasena && (
              <div className="invalid-feedback">{errores.confirmarContrasena}</div>
            )}
          </div>

          <div className="mb-3">
            <label htmlFor="palabraSecreta" className="form-label">
              Palabra secreta de recuperación
            </label>
            <input
              id="palabraSecreta"
              type="text"
              className={`form-control ${errores.palabraSecreta ? 'is-invalid' : ''}`}
              value={palabraSecreta}
              onChange={(evento) => setPalabraSecreta(evento.target.value)}
              disabled={estaEnviando}
            />
            {errores.palabraSecreta ? (
              <div className="invalid-feedback">{errores.palabraSecreta}</div>
            ) : (
              <div className="form-text">
                La usarás si olvidas tu contraseña. Guárdala en un lugar seguro.
              </div>
            )}
          </div>

          <button type="submit" className="btn btn-primary w-100" disabled={estaEnviando}>
            {estaEnviando ? 'Registrando...' : 'Registrarme'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default RegisterPage