/** URL base del backend. En desarrollo apunta a Django local; en producción se define con VITE_API_BASE_URL. */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '') || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')

/** Prefijo de versión definido en el contrato de API (sección 0). */
export const PREFIJO_API = '/api/v1'