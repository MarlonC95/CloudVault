export interface DatosNuevoEnlace {
  archivoId: string
  /** Fecha ISO de caducidad. Si se omite, el backend usa 7 días. */
  expiraEn?: string
  password?: string | null
  permiteDescarga: boolean
}

export interface EnlaceCompartido {
  id: string
  urlCompartida: string
  token: string
  passwordProtegido: boolean
  permiteDescarga: boolean
}

export interface EnlaceActivo {
  id: string
  nombreArchivo: string
  token: string
  activo: boolean
}

export interface RecursoPublico {
  nombre: string
  tipo: string
  tamanoLegible: string
  urlDescarga: string
  permiteDescarga: boolean
  expiraEn: string
}