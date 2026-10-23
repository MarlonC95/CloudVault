import axios from 'axios'
import { API_BASE_URL, PREFIJO_API } from './configuracionApi'
import { ErrorApi, convertirEnErrorApi } from './errorApi'
import type { DatosLogin, DatosRecuperacion, DatosRegistro, RespuestaLogin, UsuarioAutenticado } from './tiposAuth'

interface RespuestaLoginApi {
  data: {
    usuario: {
      id: string
      nombre_completo: string
      correo_electronico: string
    }
    tokens: {
      access: string
      refresh: string
    }
  }
}

interface RespuestaRenovacionApi {
  data: {
    access: string
    refresh?: string
  }
}

interface SesionActiva {
  usuario: UsuarioAutenticado
  accessToken: string
  venceEnMs: number
  refreshToken: string
  /** 0 significa que no pudimos leer la fecha del refresh token; en ese caso decide el servidor. */
  refreshVenceEnMs: number
}

let sesionActiva: SesionActiva | null = null

interface RespuestaRegistroApi {
  data: {
    id: string
    nombre_completo: string
    correo_electronico: string
  }
}

interface RespuestaErrorApi {
  error?: {
    code?: string
    fields?: Record<string, string[]>
  }
}

export class ErrorRegistro extends Error {
  readonly campos: Record<string, string[]>

  constructor(
    message: string,
    campos: Record<string, string[]> = {},
  ) {
    super(message)
    this.name = 'ErrorRegistro'
    this.campos = campos
  }
}

export class ErrorLogin extends Error {
  readonly campos: Record<string, string[]>

  constructor(message: string, campos: Record<string, string[]> = {}) {
    super(message)
    this.name = 'ErrorLogin'
    this.campos = campos
  }
}

export class ErrorRecuperacion extends Error {
  readonly campos: Record<string, string[]>

  constructor(message: string, campos: Record<string, string[]> = {}) {
    super(message)
    this.name = 'ErrorRecuperacion'
    this.campos = campos
  }
}

function vencimientoJwt(token: string): number {
  try {
    const payloadBase64 = token.split('.')[1]
    const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : 0
  } catch {
    return 0
  }
}

/**
 * Devuelve la sesión mientras el refresh token siga vigente. El access token dura 15 minutos,
 * pero se renueva solo (ver clienteApi.ts), así que su vencimiento ya no cierra la sesión.
 */
export function obtenerSesion(): SesionActiva | null {
  if (sesionActiva && (sesionActiva.refreshVenceEnMs === 0 || Date.now() < sesionActiva.refreshVenceEnMs)) {
    return sesionActiva
  }
  sesionActiva = null
  return null
}

export function cerrarSesion(): void {
  sesionActiva = null
}

/**
 * Crea una identidad sin iniciar sesión. El servidor genera los hashes de los secretos.
 */
export async function registrarUsuario(datos: DatosRegistro): Promise<UsuarioAutenticado> {
  try {
    const respuesta = await axios.post<RespuestaRegistroApi>(
      `${API_BASE_URL}${PREFIJO_API}/auth/registro/`,
      {
        nombre_completo: datos.nombreCompleto.trim(),
        correo_electronico: datos.correoElectronico.trim().toLowerCase(),
        contrasena: datos.contrasena,
        palabra_secreta: datos.palabraSecreta,
      },
      { headers: { 'Content-Type': 'application/json' }, withCredentials: false },
    )

    if (respuesta.status !== 201 || !respuesta.data?.data) {
      throw new ErrorRegistro('La respuesta del servidor no es válida. Intenta de nuevo.')
    }

    return {
      id: respuesta.data.data.id,
      nombreCompleto: respuesta.data.data.nombre_completo,
      correoElectronico: respuesta.data.data.correo_electronico,
    }
  } catch (error) {
    if (error instanceof ErrorRegistro) throw error
    if (!axios.isAxiosError<RespuestaErrorApi>(error)) {
      throw new ErrorRegistro('No se pudo completar el registro. Intenta de nuevo.')
    }

    const codigo = error.response?.data?.error?.code
    if (codigo === 'VALIDATION_ERROR') {
      throw new ErrorRegistro('Revisa los datos enviados.', error.response?.data?.error?.fields)
    }
    if (codigo === 'CORREO_EN_USO') {
      throw new ErrorRegistro('No se pudo completar el registro con ese correo. Puedes iniciar sesión o recuperar tu cuenta.')
    }
    if (codigo === 'RATE_LIMITED') {
      throw new ErrorRegistro('Demasiados intentos. Espera antes de volver a intentarlo.')
    }
    if (codigo === 'SERVICE_UNAVAILABLE') {
      throw new ErrorRegistro('El servicio no está disponible en este momento. Intenta más tarde.')
    }
    if (!error.response) {
      throw new ErrorRegistro('No se pudo conectar con la API. Revisa tu conexión e intenta de nuevo.')
    }
    throw new ErrorRegistro('No se pudo completar el registro. Intenta de nuevo.')
  }
}

/** Comprueba las credenciales con la API y conserva solo el acceso en memoria. */
export async function iniciarSesion(datos: DatosLogin): Promise<RespuestaLogin> {
  try {
    const respuesta = await axios.post<RespuestaLoginApi>(
      `${API_BASE_URL}${PREFIJO_API}/auth/login/`,
      {
        correo: datos.correoElectronico.trim().toLowerCase(),
        contrasena: datos.contrasena,
      },
      { headers: { 'Content-Type': 'application/json' }, withCredentials: false },
    )
    const data = respuesta.data?.data
    const venceEnMs = vencimientoJwt(data?.tokens?.access ?? '')
    if (
      respuesta.status !== 200 || !data?.usuario?.id || !data?.tokens?.refresh
      || venceEnMs <= Date.now()
    ) {
      throw new ErrorLogin('La respuesta del servidor no es válida. Intenta de nuevo.')
    }

    const usuario = {
      id: data.usuario.id,
      nombreCompleto: data.usuario.nombre_completo,
      correoElectronico: data.usuario.correo_electronico,
    }
    sesionActiva = {
      usuario,
      accessToken: data.tokens.access,
      venceEnMs,
      refreshToken: data.tokens.refresh,
      refreshVenceEnMs: vencimientoJwt(data.tokens.refresh),
    }
    return {
      accessToken: data.tokens.access,
      refreshToken: data.tokens.refresh,
      usuario,
    }
  } catch (error) {
    if (error instanceof ErrorLogin) throw error
    if (!axios.isAxiosError<RespuestaErrorApi>(error)) {
      throw new ErrorLogin('No se pudo iniciar sesión. Intenta de nuevo.')
    }

    const codigo = error.response?.data?.error?.code
    if (codigo === 'VALIDATION_ERROR') {
      throw new ErrorLogin('Revisa los datos enviados.', error.response?.data?.error?.fields)
    }
    if (codigo === 'INVALID_CREDENTIALS') {
      throw new ErrorLogin('Correo o contraseña incorrectos.')
    }
    if (codigo === 'RATE_LIMITED') {
      throw new ErrorLogin('Demasiados intentos. Espera antes de volver a intentarlo.')
    }
    if (codigo === 'SERVICE_UNAVAILABLE') {
      throw new ErrorLogin('El servicio no está disponible en este momento. Intenta más tarde.')
    }
    if (!error.response) {
      throw new ErrorLogin('No se pudo conectar con la API. Revisa tu conexión e intenta de nuevo.')
    }
    throw new ErrorLogin('No se pudo iniciar sesión. Intenta de nuevo.')
  }
}

/** Verifica la frase secreta en el servidor y cambia la contraseña. */
export async function recuperarContrasena(datos: DatosRecuperacion): Promise<void> {
  try {
    const respuesta = await axios.post<{ mensaje: string }>(
      `${API_BASE_URL}${PREFIJO_API}/auth/recuperar-contrasena/`,
      {
        correo: datos.correoElectronico.trim().toLowerCase(),
        palabra_secreta: datos.palabraSecreta,
        nueva_contrasena: datos.nuevaContrasena,
        confirmar_contrasena: datos.confirmarNuevaContrasena,
      },
      { headers: { 'Content-Type': 'application/json' }, withCredentials: false },
    )

    if (respuesta.status !== 200 || typeof respuesta.data?.mensaje !== 'string') {
      throw new ErrorRecuperacion('La respuesta del servidor no es válida. Intenta de nuevo.')
    }
    cerrarSesion()
  } catch (error) {
    if (error instanceof ErrorRecuperacion) throw error
    if (!axios.isAxiosError<RespuestaErrorApi>(error)) {
      throw new ErrorRecuperacion('No se pudo restablecer la contraseña. Intenta de nuevo.')
    }

    const codigo = error.response?.data?.error?.code
    if (codigo === 'VALIDATION_ERROR') {
      throw new ErrorRecuperacion('Revisa los datos enviados.', error.response?.data?.error?.fields)
    }
    if (codigo === 'RECOVERY_VERIFICATION_FAILED') {
      throw new ErrorRecuperacion('No fue posible verificar los datos proporcionados.')
    }
    if (codigo === 'RATE_LIMITED') {
      throw new ErrorRecuperacion('Demasiados intentos. Espera antes de volver a intentarlo.')
    }
    if (codigo === 'SERVICE_UNAVAILABLE') {
      throw new ErrorRecuperacion('El servicio no está disponible en este momento. Intenta más tarde.')
    }
    if (!error.response) {
      throw new ErrorRecuperacion('No se pudo conectar con la API. Revisa tu conexión e intenta de nuevo.')
    }
    throw new ErrorRecuperacion('No se pudo restablecer la contraseña. Intenta de nuevo.')
  }
}

let renovacionEnCurso: Promise<string> | null = null

async function solicitarNuevoAccessToken(): Promise<string> {
  const sesion = obtenerSesion()
  if (!sesion) throw new ErrorApi('TOKEN_INVALIDO')

  try {
    const respuesta = await axios.post<RespuestaRenovacionApi>(
      `${API_BASE_URL}${PREFIJO_API}/auth/refresh/`,
      { refresh: sesion.refreshToken },
      { headers: { 'Content-Type': 'application/json' }, withCredentials: false },
    )
    const { access, refresh } = respuesta.data.data
    const venceEnMs = vencimientoJwt(access)
    if (venceEnMs <= Date.now()) throw new ErrorApi('TOKEN_INVALIDO')

    sesionActiva = {
      ...sesion,
      accessToken: access,
      venceEnMs,
      refreshToken: refresh ?? sesion.refreshToken,
      refreshVenceEnMs: refresh ? vencimientoJwt(refresh) : sesion.refreshVenceEnMs,
    }
    return access
  } catch (error) {
    throw convertirEnErrorApi(error)
  }
}

/**
 * Pide un access token nuevo con el refresh token (POST /auth/refresh/).
 * Si varias peticiones fallan a la vez, todas comparten una sola renovación.
 */
export function renovarAccessToken(): Promise<string> {
  if (!renovacionEnCurso) {
    renovacionEnCurso = solicitarNuevoAccessToken().finally(() => {
      renovacionEnCurso = null
    })
  }
  return renovacionEnCurso
}

/**
 * Cierra la sesión: la borra de la memoria y avisa al servidor para invalidar el refresh token
 * (POST /auth/logout/). Si el servidor no responde, la sesión local se cierra igual.
 */
export async function cerrarSesionEnServidor(): Promise<void> {
  const sesion = obtenerSesion()
  cerrarSesion()
  if (!sesion) return

  try {
    await axios.post(
      `${API_BASE_URL}${PREFIJO_API}/auth/logout/`,
      { refresh: sesion.refreshToken },
      { headers: { Authorization: `Bearer ${sesion.accessToken}` }, withCredentials: false },
    )
  } catch {
    // Mejor esfuerzo: el usuario ya salió de la app aunque el servidor no haya podido registrarlo.
  }
}