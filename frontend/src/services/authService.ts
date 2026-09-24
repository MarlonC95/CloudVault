import type { DatosLogin, DatosRecuperacion,  DatosRegistro, RespuestaLogin, UsuarioAutenticado } from './tiposAuth'

const RETARDO_SIMULADO_MS = 800

/**
 * Registra un nuevo usuario.
 * TODO(backend): reemplazar por la llamada real con axios a POST /api/auth/register/
 */
export async function registrarUsuario(datos: DatosRegistro): Promise<UsuarioAutenticado> {
  console.log('[authService] Simulando registro con:', datos)

  await new Promise((resolve) => setTimeout(resolve, RETARDO_SIMULADO_MS))

  return {
    id: 'simulado-123',
    nombreCompleto: datos.nombreCompleto,
    correoElectronico: datos.correoElectronico,
  }
}

/**
 * Inicia sesión con correo y contraseña.
 * TODO(backend): reemplazar por la llamada real con axios a POST /api/auth/login/
 */
export async function iniciarSesion(datos: DatosLogin): Promise<RespuestaLogin> {
  console.log('[authService] Simulando login con:', datos)

  await new Promise((resolve) => setTimeout(resolve, RETARDO_SIMULADO_MS))

  return {
    accessToken: 'token-simulado-abc',
    refreshToken: 'refresh-simulado-xyz',
    usuario: {
      id: 'simulado-123',
      nombreCompleto: 'Usuario de prueba',
      correoElectronico: datos.correoElectronico,
    },
  }
}

// ...

/**
 * Restablece la contraseña usando la palabra secreta como verificación.
 * TODO(backend): reemplazar por la llamada real con axios a POST /api/auth/recuperar-password/
 */
export async function recuperarContrasena(datos: DatosRecuperacion): Promise<void> {
  console.log('[authService] Simulando recuperación con:', datos)
  await new Promise((resolve) => setTimeout(resolve, RETARDO_SIMULADO_MS))
}