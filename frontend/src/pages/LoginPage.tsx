import { useState } from 'react'
import { iniciarSesion } from '../services/authService'

interface ErroresLogin {
  correoElectronico?: string
  contrasena?: string
}

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
    <div className="d-flex justify-content-center align-items-center vh-100 bg-light">
      <div className="card p-4 shadow-sm" style={{ width: '400px' }}>
        <h2 className="mb-4 text-center">Iniciar sesión</h2>

        {errorGeneral && <div className="alert alert-danger">{errorGeneral}</div>}

        <form onSubmit={manejarEnvio} noValidate>
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

          <button type="submit" className="btn btn-primary w-100" disabled={estaEnviando}>
            {estaEnviando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage