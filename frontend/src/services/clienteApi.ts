import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { API_BASE_URL, PREFIJO_API } from './configuracionApi'
import { cerrarSesion, obtenerSesion, renovarAccessToken } from './authService'
import { convertirEnErrorApi } from './errorApi'

/** Rutas donde un 401 significa "datos incorrectos", no "token vencido": ahí no tiene sentido renovar. */
const RUTAS_SIN_RENOVACION = ['/auth/login/', '/auth/registro/', '/auth/recuperar-contrasena/', '/auth/refresh/']

/**
 * Cliente HTTP para todos los endpoints protegidos de la API.
 *  - Agrega `Authorization: Bearer <access>` a cada petición.
 *  - Si el backend responde 401, renueva el token y repite la petición una sola vez (Apéndice B del contrato).
 *  - Cualquier fallo llega a los componentes como un `ErrorApi` (ver errorApi.ts).
 */
export const clienteApi = axios.create({
  baseURL: `${API_BASE_URL}${PREFIJO_API}`,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
})

const peticionesReintentadas = new WeakSet<InternalAxiosRequestConfig>()

function debeRenovarToken(error: AxiosError): boolean {
  const peticion = error.config
  if (error.response?.status !== 401 || !peticion) return false
  if (peticionesReintentadas.has(peticion)) return false
  if (obtenerSesion() === null) return false

  const url = peticion.url ?? ''
  return !RUTAS_SIN_RENOVACION.some((ruta) => url.includes(ruta))
}

/**
 * Si la petición falló con un token que ya fue reemplazado (otra petición lo renovó mientras tanto),
 * basta con reutilizar el nuevo. Solo se pide una renovación cuando el token fallido sigue siendo el actual.
 */
async function obtenerAccessTokenVigente(peticionFallida: InternalAxiosRequestConfig): Promise<string> {
  const tokenActual = obtenerSesion()?.accessToken
  const tokenUsado = peticionFallida.headers.Authorization
  if (tokenActual && tokenUsado !== `Bearer ${tokenActual}`) return tokenActual
  return renovarAccessToken()
}

function volverAlLogin() {
  cerrarSesion()
  if (window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

clienteApi.interceptors.request.use((peticion) => {
  const sesion = obtenerSesion()
  if (sesion) {
    peticion.headers.Authorization = `Bearer ${sesion.accessToken}`
  }
  return peticion
})

clienteApi.interceptors.response.use(
  (respuesta) => respuesta,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !debeRenovarToken(error)) {
      throw convertirEnErrorApi(error)
    }

    const peticionOriginal = error.config!
    try {
      const nuevoAccessToken = await obtenerAccessTokenVigente(peticionOriginal)
      peticionesReintentadas.add(peticionOriginal)
      peticionOriginal.headers.Authorization = `Bearer ${nuevoAccessToken}`
      return await clienteApi.request(peticionOriginal)
    } catch (errorAlReintentar) {
      // Si la renovación falló, la sesión ya no sirve. Si falló el reintento, el error es el real de esa petición.
      const errorConvertido = convertirEnErrorApi(errorAlReintentar)
      if (errorConvertido.codigo === 'TOKEN_INVALIDO' || errorConvertido.codigo === 'NO_AUTENTICADO') {
        volverAlLogin()
      }
      throw errorConvertido
    }
  },
)