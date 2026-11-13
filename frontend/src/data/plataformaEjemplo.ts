import type {
  DesgloseAlmacenamiento,
  EventoPlataforma,
  OrganizacionPlataforma,
  ResumenPlataforma,
  UsuarioPlataforma,
} from '../types/plataforma'

// TODO(backend): datos de ejemplo. Cuando existan los endpoints del contrato (sección 6) se reemplazan
// por llamadas a un plataformaService:
//   GET /admin/metricas/resumen/  ·  GET /admin/metricas/almacenamiento/  ·  GET /admin/usuarios/
//   GET /admin/organizaciones/    ·  GET /admin/auditoria/                 ·  PATCH /admin/usuarios/{id}/estado/

const MS_POR_HORA = 60 * 60 * 1000
const MS_POR_DIA = 24 * MS_POR_HORA

function haceHoras(horas: number): string {
  return new Date(Date.now() - horas * MS_POR_HORA).toISOString()
}

function haceDias(dias: number): string {
  return new Date(Date.now() - dias * MS_POR_DIA).toISOString()
}

export const RESUMEN_PLATAFORMA_EJEMPLO: ResumenPlataforma = {
  totalUsuariosRegistrados: 8,
  usuariosActivosPeriodo: 6,
  totalOrganizaciones: 6,
  almacenamientoAgregadoLegible: '182 GB',
  ingresosMensualesEstimadosUsd: '84.00',
  ingresosSimuladosPeriodoUsd: '58.00',
  desde: haceDias(29),
  hasta: new Date().toISOString(),
  distribucionPlanes: { BASICO: 3, PREMIUM: 2, EMPRESARIAL_PLATINUM: 1 },
}

export const DESGLOSE_ALMACENAMIENTO_EJEMPLO: DesgloseAlmacenamiento = {
  porTipo: [
    { tipo: 'application/pdf', tamanoLegible: '73 GB', porcentaje: 40 },
    { tipo: 'video/mp4', tamanoLegible: '55 GB', porcentaje: 30 },
    { tipo: 'image/jpeg', tamanoLegible: '36 GB', porcentaje: 20 },
    { tipo: 'otros', tamanoLegible: '18 GB', porcentaje: 10 },
  ],
  papeleraLegible: '9 GB',
}

export const USUARIOS_PLATAFORMA_EJEMPLO: UsuarioPlataforma[] = [
  { id: 'usuario-1', nombreCompleto: 'Mily Santay', correoElectronico: 'mily.santay@empresa.com', estaActivo: true, organizacionesCount: 2, almacenamientoPropietarioLegible: '45 GB', fechaRegistro: haceDias(120) },
  { id: 'usuario-2', nombreCompleto: 'Carlos López', correoElectronico: 'carlos.lopez@empresa.com', estaActivo: true, organizacionesCount: 2, almacenamientoPropietarioLegible: '32 GB', fechaRegistro: haceDias(98) },
  { id: 'usuario-3', nombreCompleto: 'Sofía Ramírez', correoElectronico: 'sofia.ramirez@empresa.com', estaActivo: true, organizacionesCount: 1, almacenamientoPropietarioLegible: '27 GB', fechaRegistro: haceDias(80) },
  { id: 'usuario-4', nombreCompleto: 'Luis Pérez', correoElectronico: 'luis.perez@empresa.com', estaActivo: true, organizacionesCount: 1, almacenamientoPropietarioLegible: '12 GB', fechaRegistro: haceDias(61) },
  { id: 'usuario-5', nombreCompleto: 'Ana García', correoElectronico: 'ana.garcia@empresa.com', estaActivo: true, organizacionesCount: 1, almacenamientoPropietarioLegible: '19 GB', fechaRegistro: haceDias(45) },
  { id: 'usuario-6', nombreCompleto: 'Marlon Castillo', correoElectronico: 'marlon.castillo@empresa.com', estaActivo: true, organizacionesCount: 1, almacenamientoPropietarioLegible: '24 GB', fechaRegistro: haceDias(30) },
  { id: 'usuario-7', nombreCompleto: 'Diego Morales', correoElectronico: 'diego.morales@empresa.com', estaActivo: false, organizacionesCount: 1, almacenamientoPropietarioLegible: '5 GB', fechaRegistro: haceDias(21) },
  { id: 'usuario-8', nombreCompleto: 'Paola Hernández', correoElectronico: 'paola.hernandez@empresa.com', estaActivo: true, organizacionesCount: 1, almacenamientoPropietarioLegible: '18 GB', fechaRegistro: haceDias(9) },
]

export const ORGANIZACIONES_PLATAFORMA_EJEMPLO: OrganizacionPlataforma[] = [
  { id: 'org-1', nombre: 'CloudVault Equipo', tipo: 'COMPARTIDO', plan: 'EMPRESARIAL_PLATINUM', almacenamientoUsadoLegible: '58 GB', fechaCreacion: haceDias(118) },
  { id: 'org-2', nombre: 'Mily Santay (personal)', tipo: 'PERSONAL', plan: 'PREMIUM', almacenamientoUsadoLegible: '27 GB', fechaCreacion: haceDias(120) },
  { id: 'org-3', nombre: 'Estudio Creativo López', tipo: 'COMPARTIDO', plan: 'PREMIUM', almacenamientoUsadoLegible: '41 GB', fechaCreacion: haceDias(90) },
  { id: 'org-4', nombre: 'Sofía Ramírez (personal)', tipo: 'PERSONAL', plan: 'BASICO', almacenamientoUsadoLegible: '19 GB', fechaCreacion: haceDias(80) },
  { id: 'org-5', nombre: 'Luis Pérez (personal)', tipo: 'PERSONAL', plan: 'BASICO', almacenamientoUsadoLegible: '12 GB', fechaCreacion: haceDias(61) },
  { id: 'org-6', nombre: 'Ana García (personal)', tipo: 'PERSONAL', plan: 'BASICO', almacenamientoUsadoLegible: '25 GB', fechaCreacion: haceDias(45) },
]

export const EVENTOS_PLATAFORMA_EJEMPLO: EventoPlataforma[] = [
  { id: 'evt-1', accion: 'LOGIN_SUCCESS', usuarioNombre: 'Carlos López', organizacionNombre: null, fechaEvento: haceHoras(1), detalles: { usuario_id: 'usuario-2' } },
  { id: 'evt-2', accion: 'FILE_UPLOADED', usuarioNombre: 'Mily Santay', organizacionNombre: 'CloudVault Equipo', fechaEvento: haceHoras(3), detalles: { archivo_id: 'archivo-88', bytes: '4398046' } },
  { id: 'evt-3', accion: 'MEMBER_INVITED', usuarioNombre: 'Mily Santay', organizacionNombre: 'CloudVault Equipo', fechaEvento: haceHoras(20), detalles: { rol: 'operativo' } },
  { id: 'evt-4', accion: 'ADMIN_USER_DISABLED', usuarioNombre: 'Marlon Castillo', organizacionNombre: null, fechaEvento: haceHoras(50), detalles: { usuario_id: 'usuario-7', motivo: 'Actividad sospechosa reportada' } },
  { id: 'evt-5', accion: 'USER_PROFILE_UPDATED', usuarioNombre: 'Ana García', organizacionNombre: null, fechaEvento: haceHoras(72), detalles: { usuario_id: 'usuario-5' } },
  { id: 'evt-6', accion: 'FILE_TRASHED', usuarioNombre: 'Luis Pérez', organizacionNombre: 'Luis Pérez (personal)', fechaEvento: haceHoras(96), detalles: { archivo_id: 'archivo-41' } },
  { id: 'evt-7', accion: 'LOGIN_SUCCESS', usuarioNombre: 'Sofía Ramírez', organizacionNombre: null, fechaEvento: haceHoras(130), detalles: { usuario_id: 'usuario-3' } },
]