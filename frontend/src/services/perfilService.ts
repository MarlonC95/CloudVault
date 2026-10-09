import { clienteApi } from './clienteApi'
import type { RespuestaApi } from '../types/api'
import type {
  DatosActualizacionPerfil,
  DatosCambioContrasena,
  DatosCambioPalabraSecreta,
  PerfilUsuario,
  PreferenciasUsuario,
  RolUsuario,
} from '../types/perfil'

interface PerfilApi {
  id: string
  nombre_completo: string
  correo_electronico: string
  rol: RolUsuario
  plan: { id: string; nombre: string }
  dos_factores: boolean
  almacenamiento: {
    usado_bytes: number
    cuota_bytes: number
    usado_legible: string
    cuota_legible: string
    porcentaje_usado: number
  }
  fecha_registro: string
}

interface PreferenciasApi {
  dos_factores: boolean
  idioma: string
  zona_horaria: string
}

function mapearPerfil(perfil: PerfilApi): PerfilUsuario {
  return {
    id: perfil.id,
    nombreCompleto: perfil.nombre_completo,
    correoElectronico: perfil.correo_electronico,
    rol: perfil.rol,
    plan: perfil.plan,
    dosFactores: perfil.dos_factores,
    almacenamiento: {
      usadoBytes: perfil.almacenamiento.usado_bytes,
      cuotaBytes: perfil.almacenamiento.cuota_bytes,
      usadoLegible: perfil.almacenamiento.usado_legible,
      cuotaLegible: perfil.almacenamiento.cuota_legible,
      porcentajeUsado: perfil.almacenamiento.porcentaje_usado,
    },
    fechaRegistro: perfil.fecha_registro,
  }
}

function mapearPreferencias(preferencias: PreferenciasApi): PreferenciasUsuario {
  return {
    dosFactores: preferencias.dos_factores,
    idioma: preferencias.idioma,
    zonaHoraria: preferencias.zona_horaria,
  }
}

/** GET /auth/perfil/ (contrato 2.1) */
export async function obtenerPerfil(): Promise<PerfilUsuario> {
  const respuesta = await clienteApi.get<RespuestaApi<PerfilApi>>('/auth/perfil/')
  return mapearPerfil(respuesta.data.data)
}

/** PATCH /auth/perfil/ (contrato 2.2): actualización parcial de nombre o correo. */
export async function actualizarPerfil(datos: DatosActualizacionPerfil): Promise<void> {
  await clienteApi.patch('/auth/perfil/', {
    nombre_completo: datos.nombreCompleto,
    correo_electronico: datos.correoElectronico?.trim().toLowerCase(),
  })
}

/** POST /auth/cambiar-contrasena/ (contrato 2.3) */
export async function cambiarContrasena(datos: DatosCambioContrasena): Promise<void> {
  await clienteApi.post('/auth/cambiar-contrasena/', {
    contrasena_actual: datos.contrasenaActual,
    nueva_contrasena: datos.nuevaContrasena,
    confirmar_contrasena: datos.confirmarContrasena,
  })
}

/** POST /auth/cambiar-palabra-secreta/ (contrato 2.4) */
export async function cambiarPalabraSecreta(datos: DatosCambioPalabraSecreta): Promise<void> {
  await clienteApi.post('/auth/cambiar-palabra-secreta/', {
    contrasena_actual: datos.contrasenaActual,
    nueva_palabra_secreta: datos.nuevaPalabraSecreta,
  })
}

/** GET /auth/preferencias/ (contrato 2.5) */
export async function obtenerPreferencias(): Promise<PreferenciasUsuario> {
  const respuesta = await clienteApi.get<RespuestaApi<PreferenciasApi>>('/auth/preferencias/')
  return mapearPreferencias(respuesta.data.data)
}

/** PATCH /auth/preferencias/ (contrato 2.6) */
export async function actualizarPreferencias(cambios: Partial<PreferenciasUsuario>): Promise<PreferenciasUsuario> {
  const respuesta = await clienteApi.patch<RespuestaApi<PreferenciasApi>>('/auth/preferencias/', {
    dos_factores: cambios.dosFactores,
    idioma: cambios.idioma,
    zona_horaria: cambios.zonaHoraria,
  })
  return mapearPreferencias(respuesta.data.data)
}