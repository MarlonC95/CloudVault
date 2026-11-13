import axios from 'axios'

/** Códigos de error del catálogo del contrato (sección 0.4) más SIN_CONEXION, que solo existe en el frontend. */
export type CodigoErrorApi =
  | 'RESOURCE_BUSY'
  | 'VALIDATION_ERROR'
  | 'INVALID_CREDENTIALS'
  | 'RECOVERY_VERIFICATION_FAILED'
  | 'NO_AUTENTICADO'
  | 'TOKEN_INVALIDO'
  | 'SIN_PERMISO'
  | 'NO_ENCONTRADO'
  | 'OWNER_REQUIRED'
  | 'PLAN_FEATURE_REQUIRED'
  | 'MEMBER_EXISTS'
  | 'INVITATION_PENDING'
  | 'INVITATION_CLOSED'
  | 'IDEMPOTENCY_CONFLICT'
  | 'CORREO_EN_USO'
  | 'CUOTA_EXCEDIDA'
  | 'RATE_LIMITED'
  | 'CONTEXT_NOT_READY'
  | 'CANDIDATE_STALE'
  | 'PURGE_INCOMPATIBLE'
  | 'RETRY_DEFERRED'
  | 'METODO_NO_PERMITIDO'
  | 'OWNER_REQUIRED'
  | 'CANNOT_REMOVE_SELF'
  | 'ERROR_INTERNO'
  | 'SERVICE_UNAVAILABLE'
  | 'SIN_CONEXION'
  | 'DESCONOCIDO'

/** Forma del cuerpo de error del contrato (sección 0.3). */
interface CuerpoErrorApi {
  error?: {
    code?: string
    fields?: Record<string, string[]>
  }
}

const MENSAJES_POR_CODIGO: Record<CodigoErrorApi, string> = {
  RESOURCE_BUSY: 'El recurso está siendo procesado. Intenta de nuevo más tarde.',
  VALIDATION_ERROR: 'Revisa los datos enviados.',
  INVALID_CREDENTIALS: 'Correo o contraseña incorrectos.',
  RECOVERY_VERIFICATION_FAILED: 'No fue posible verificar los datos proporcionados.',
  NO_AUTENTICADO: 'Debes iniciar sesión para continuar.',
  TOKEN_INVALIDO: 'Tu sesión expiró. Inicia sesión de nuevo.',
  SIN_PERMISO: 'No tienes permiso para realizar esta acción.',
  NO_ENCONTRADO: 'No encontramos lo que buscas.',
  OWNER_REQUIRED: 'El propietario de la organización no puede modificarse ni retirarse.',
  PLAN_FEATURE_REQUIRED: 'Esta operación requiere una organización compartida con un plan vigente.',
  MEMBER_EXISTS: 'La cuenta ya pertenece a esta organización.',
  INVITATION_PENDING: 'Ya existe una invitación pendiente con otro rol. Revócala antes de enviar una nueva.',
  INVITATION_CLOSED: 'La invitación ya fue resuelta o venció.',
  IDEMPOTENCY_CONFLICT: 'La solicitud ya se usó con datos distintos. Abre un nuevo formulario.',
  CORREO_EN_USO: 'Ese correo ya está registrado. Puedes iniciar sesión o recuperar tu cuenta.',
  CUOTA_EXCEDIDA: 'No tienes almacenamiento suficiente para esta operación.',
  RATE_LIMITED: 'Demasiados intentos. Espera antes de volver a intentarlo.',
  CONTEXT_NOT_READY: 'La organización aún no está lista. Intenta de nuevo en unos segundos.',
  CANDIDATE_STALE: 'El estado del elemento cambió. Actualiza la vista e intenta de nuevo.',
  PURGE_INCOMPATIBLE: 'La selección de vaciado ya no coincide con el estado actual de la papelera.',
  RETRY_DEFERRED: 'La operación aún tiene elementos en espera. Intenta de nuevo en unos segundos.',
  METODO_NO_PERMITIDO: 'Operación no permitida en este recurso.',
  OWNER_REQUIRED: 'La organización debe conservar al menos un propietario activo.',
  CANNOT_REMOVE_SELF: 'No puedes retirarte a ti mismo de la organización desde este panel.',
  ERROR_INTERNO: 'Ocurrió un error en el servidor. Intenta más tarde.',
  SERVICE_UNAVAILABLE: 'El servicio no está disponible en este momento. Intenta más tarde.',
  SIN_CONEXION: 'No se pudo conectar con la API. Revisa tu conexión e intenta de nuevo.',
  DESCONOCIDO: 'Ocurrió un error inesperado. Intenta de nuevo.',
}

const ALIAS_CODIGOS: Partial<Record<string, CodigoErrorApi>> = {
  FORBIDDEN: 'SIN_PERMISO',
  NOT_FOUND: 'NO_ENCONTRADO',
  TOKEN_INVALID: 'TOKEN_INVALIDO',
}

function esCodigoConocido(codigo: string): codigo is CodigoErrorApi {
  return Object.hasOwn(MENSAJES_POR_CODIGO, codigo)
}

/**
 * Error estándar de la API. Los componentes lo atrapan con `catch` y leen:
 *  - `codigo`: el `error.code` del contrato
 *  - `campos`: el diccionario `error.fields` (mensajes por campo)
 *  - `message`: un texto en español listo para mostrar
 */
export class ErrorApi extends Error {
  readonly codigo: CodigoErrorApi
  readonly campos: Record<string, string[]>
  readonly estadoHttp: number | null

  constructor(codigo: CodigoErrorApi, campos: Record<string, string[]> = {}, estadoHttp: number | null = null) {
    super(MENSAJES_POR_CODIGO[codigo])
    this.name = 'ErrorApi'
    this.codigo = codigo
    this.campos = campos
    this.estadoHttp = estadoHttp
  }
}

/** Traduce cualquier error (de Axios o no) a un ErrorApi leyendo `response.data.error.code` y `.fields`. */
export function convertirEnErrorApi(error: unknown): ErrorApi {
  if (error instanceof ErrorApi) return error

  if (!axios.isAxiosError<CuerpoErrorApi>(error)) return new ErrorApi('DESCONOCIDO')
  if (!error.response) return new ErrorApi('SIN_CONEXION')

  const { status, data } = error.response
  const codigoOriginal = data?.error?.code
  const codigoRecibido = codigoOriginal && (Object.hasOwn(ALIAS_CODIGOS, codigoOriginal)
    ? ALIAS_CODIGOS[codigoOriginal]
    : codigoOriginal)
  const campos = data?.error?.fields ?? {}

  if (codigoRecibido && esCodigoConocido(codigoRecibido)) {
    return new ErrorApi(codigoRecibido, campos, status)
  }
  if (status >= 500) return new ErrorApi('ERROR_INTERNO', campos, status)
  return new ErrorApi('DESCONOCIDO', campos, status)
}

/** Devuelve el primer mensaje de validación de un campo, o undefined si no hay. */
export function obtenerMensajeDeCampo(error: ErrorApi, campo: string): string | undefined {
  return error.campos[campo]?.[0]
}