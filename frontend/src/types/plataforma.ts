/** Códigos de plan que usa el contrato (sección 6). */
export type CodigoPlan = 'BASICO' | 'PREMIUM' | 'EMPRESARIAL_PLATINUM'

export type TipoOrganizacion = 'PERSONAL' | 'COMPARTIDO'

export type PestanaPlataforma = 'resumen' | 'usuarios' | 'organizaciones' | 'auditoria'

/** Métricas globales: GET /admin/metricas/resumen/ */
export interface ResumenPlataforma {
  totalUsuariosRegistrados: number
  usuariosActivosPeriodo: number
  totalOrganizaciones: number
  almacenamientoAgregadoLegible: string
  /** Importes como texto decimal con dos posiciones, igual que el contrato ("4850.00"). */
  ingresosMensualesEstimadosUsd: string
  ingresosSimuladosPeriodoUsd: string
  /** Inicio y fin del periodo en ISO (UTC). */
  desde: string
  hasta: string
  distribucionPlanes: Record<CodigoPlan, number>
}

export interface AlmacenamientoPorTipo {
  /** Tipo MIME tal como lo devuelve el contrato, o "otros". */
  tipo: string
  tamanoLegible: string
  porcentaje: number
}

/** Desglose de almacenamiento: GET /admin/metricas/almacenamiento/ */
export interface DesgloseAlmacenamiento {
  porTipo: AlmacenamientoPorTipo[]
  papeleraLegible: string
}

/** Fila del listado administrativo: GET /admin/usuarios/ */
export interface UsuarioPlataforma {
  id: string
  nombreCompleto: string
  correoElectronico: string
  estaActivo: boolean
  organizacionesCount: number
  almacenamientoPropietarioLegible: string
  fechaRegistro: string
}

/** Fila del catálogo: GET /admin/organizaciones/ */
export interface OrganizacionPlataforma {
  id: string
  nombre: string
  tipo: TipoOrganizacion
  plan: CodigoPlan
  almacenamientoUsadoLegible: string
  fechaCreacion: string
}

/** Evento del registro global: GET /admin/auditoria/ */
export interface EventoPlataforma {
  id: string
  /** Código de la acción, por ejemplo "ADMIN_USER_DISABLED". */
  accion: string
  usuarioNombre: string | null
  organizacionNombre: string | null
  fechaEvento: string
  detalles: Record<string, string>
}