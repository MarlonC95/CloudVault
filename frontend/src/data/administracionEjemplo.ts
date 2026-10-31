import type { EventoAuditoria, MiembroOrganizacion, ResumenOrganizacion } from '../types/administracion'

// TODO(backend): estos datos son de ejemplo. Cuando existan los endpoints del contrato (sección 6),
// se reemplazan por llamadas a un administracionService:
//   GET /organizaciones/{id}/miembros/   ·   GET /organizaciones/{id}/auditoria/

const MS_POR_HORA = 60 * 60 * 1000

function haceHoras(horas: number): string {
  return new Date(Date.now() - horas * MS_POR_HORA).toISOString()
}

export const RESUMEN_ORGANIZACION_EJEMPLO: ResumenOrganizacion = {
  almacenamientoUsadoLegible: '45 GB',
  cuotaLegible: '100 GB',
  porcentajeAlmacenamiento: 45,
  disponibilidadServicio: '99.9%',
}

export const MIEMBROS_EJEMPLO: MiembroOrganizacion[] = [
  { id: 'miembro-1', nombreCompleto: 'Mily Santay', correoElectronico: 'mily.santay@empresa.com', rol: 'propietario', estado: 'activo' },
  { id: 'miembro-2', nombreCompleto: 'Carlos López', correoElectronico: 'carlos.lopez@empresa.com', rol: 'avanzado', estado: 'activo' },
  { id: 'miembro-3', nombreCompleto: 'Sofía Ramírez', correoElectronico: 'sofia.ramirez@empresa.com', rol: 'operativo', estado: 'activo' },
  { id: 'miembro-4', nombreCompleto: 'Luis Pérez', correoElectronico: 'luis.perez@empresa.com', rol: 'lector', estado: 'activo' },
  { id: 'miembro-5', nombreCompleto: 'Ana García', correoElectronico: 'ana.garcia@empresa.com', rol: 'operativo', estado: 'pendiente' },
]

export const EVENTOS_EJEMPLO: EventoAuditoria[] = [
  { id: 'evento-1', tipo: 'subida', descripcion: 'Mily Santay subió Arquitectura_PaaS_v1.pdf', fecha: haceHoras(2), severidad: 'info' },
  { id: 'evento-2', tipo: 'eliminacion', descripcion: 'Carlos López eliminó Temp_cache.log', fecha: haceHoras(20), severidad: 'advertencia' },
  { id: 'evento-3', tipo: 'seguridad', descripcion: 'Acceso detectado desde una nueva dirección IP', fecha: haceHoras(60), severidad: 'critica' },
  { id: 'evento-4', tipo: 'subida', descripcion: 'Sofía Ramírez subió Presupuesto_Q4.xlsx', fecha: haceHoras(75), severidad: 'info' },
  { id: 'evento-5', tipo: 'eliminacion', descripcion: 'Luis Pérez eliminó Borrador_manual.docx', fecha: haceHoras(130), severidad: 'advertencia' },
  { id: 'evento-6', tipo: 'subida', descripcion: 'Carlos López subió Diagrama_BD.png', fecha: haceHoras(200), severidad: 'info' },
]