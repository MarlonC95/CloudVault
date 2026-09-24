export interface DatosRegistro {
  nombreCompleto: string
  correoElectronico: string
  contrasena: string
  palabraSecreta: string
}

export interface DatosLogin {
  correoElectronico: string
  contrasena: string
}

export interface UsuarioAutenticado {
  id: string
  nombreCompleto: string
  correoElectronico: string
}

export interface RespuestaLogin {
  accessToken: string
  refreshToken: string
  usuario: UsuarioAutenticado
}

export interface DatosRecuperacion {
  correoElectronico: string
  palabraSecreta: string
  nuevaContrasena: string
}