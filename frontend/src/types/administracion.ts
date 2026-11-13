/** Roles de una organización según el contrato: nivel_rol 0 (propietario) a 3. */
export type RolMiembro = 'propietario' | 'avanzado' | 'operativo' | 'lector'

export type EstadoMiembro = 'activo' | 'pendiente'

export interface MiembroOrganizacion {
  id: string
  nombreCompleto: string
  correoElectronico: string
  rol: RolMiembro
  estado: EstadoMiembro
}

export type TipoEvento = 'subida' | 'eliminacion' | 'seguridad'

export type SeveridadEvento = 'info' | 'advertencia' | 'critica'

export interface EventoAuditoria {
  id: string
  tipo: TipoEvento
  descripcion: string
  /** Fecha ISO (UTC). La pantalla la muestra en lenguaje cercano ("Hace 2 horas"). */
  fecha: string
  severidad: SeveridadEvento
}

/** Cifras del resumen de la organización que se muestran en las tarjetas superiores. */
export interface ResumenOrganizacion {
  almacenamientoUsadoLegible: string
  cuotaLegible: string
  porcentajeAlmacenamiento: number
  disponibilidadServicio: string
}