export type RolUsuario = 'admin' | 'usuario'

export interface PlanResumen {
  id: string
  nombre: string
}

export interface AlmacenamientoUsuario {
  usadoBytes: number
  cuotaBytes: number
  usadoLegible: string
  cuotaLegible: string
  porcentajeUsado: number
}

export interface PerfilUsuario {
  id: string
  nombreCompleto: string
  correoElectronico: string
  rol: RolUsuario
  plan: PlanResumen
  dosFactores: boolean
  almacenamiento: AlmacenamientoUsuario
  fechaRegistro: string
}

export interface PreferenciasUsuario {
  dosFactores: boolean
  idioma: string
  zonaHoraria: string
}

export interface DatosActualizacionPerfil {
  nombreCompleto?: string
  correoElectronico?: string
}

export interface DatosCambioContrasena {
  contrasenaActual: string
  nuevaContrasena: string
  confirmarContrasena: string
}

export interface DatosCambioPalabraSecreta {
  contrasenaActual: string
  nuevaPalabraSecreta: string
}