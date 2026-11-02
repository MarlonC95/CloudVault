/**
 * Destino tras iniciar sesión según `?next=`. Solo se aceptan rutas del mismo origen: una URL
 * absoluta, `//host`, `/\host` o `javascript:` vuelven al dashboard (evita la redirección abierta).
 */
export function destinoTrasLogin(search: string, origen = window.location.origin): string {
  const next = new URLSearchParams(search).get('next')
  if (!next) return '/dashboard'
  try {
    const url = new URL(next, origen)
    return url.origin === origen ? url.pathname + url.search + url.hash : '/dashboard'
  } catch {
    return '/dashboard'
  }
}
