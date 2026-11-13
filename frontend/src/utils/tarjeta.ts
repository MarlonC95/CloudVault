import type { DatosTarjeta, ErroresTarjeta, MarcaTarjeta } from '../types/pago'

/** Tarjetas de prueba de la simulación: una se aprueba y la otra siempre se rechaza. */
export const TARJETA_PRUEBA_APROBADA = '4242 4242 4242 4242'
export const TARJETA_PRUEBA_RECHAZADA = '4000 0000 0000 0002'

const NOMBRES_MARCA: Record<MarcaTarjeta, string> = {
  visa: 'Visa',
  mastercard: 'Mastercard',
  amex: 'American Express',
  desconocida: 'Tarjeta',
}

const ANIOS_MAXIMOS_DE_VIGENCIA = 20

export function soloDigitos(texto: string): string {
  return texto.replace(/\D/g, '')
}

export function detectarMarca(numero: string): MarcaTarjeta {
  const digitos = soloDigitos(numero)
  if (/^3[47]/.test(digitos)) return 'amex'
  if (/^4/.test(digitos)) return 'visa'
  if (/^(5[1-5]|2[2-7])/.test(digitos)) return 'mastercard'
  return 'desconocida'
}

export function obtenerNombreMarca(marca: MarcaTarjeta): string {
  return NOMBRES_MARCA[marca]
}

function longitudNumero(marca: MarcaTarjeta): number {
  return marca === 'amex' ? 15 : 16
}

export function longitudCvv(marca: MarcaTarjeta): number {
  return marca === 'amex' ? 4 : 3
}

/** "4242424242424242" -> "4242 4242 4242 4242" (American Express usa grupos 4-6-5). */
export function formatearNumeroTarjeta(texto: string): string {
  const marca = detectarMarca(texto)
  const digitos = soloDigitos(texto).slice(0, longitudNumero(marca))
  if (marca === 'amex') {
    return [digitos.slice(0, 4), digitos.slice(4, 10), digitos.slice(10)].filter(Boolean).join(' ')
  }
  return digitos.replace(/(\d{4})(?=\d)/g, '$1 ')
}

/** "1228" -> "12/28". */
export function formatearVencimiento(texto: string): string {
  const digitos = soloDigitos(texto).slice(0, 4)
  return digitos.length > 2 ? `${digitos.slice(0, 2)}/${digitos.slice(2)}` : digitos
}

/** Algoritmo de Luhn: detecta números de tarjeta mal escritos. */
export function pasaLuhn(numero: string): boolean {
  const digitos = soloDigitos(numero)
  let suma = 0
  for (let indice = 0; indice < digitos.length; indice++) {
    let digito = Number(digitos[digitos.length - 1 - indice])
    if (indice % 2 === 1) {
      digito *= 2
      if (digito > 9) digito -= 9
    }
    suma += digito
  }
  return digitos.length > 0 && suma % 10 === 0
}

/** La tarjeta vale hasta el último día del mes indicado. */
function esVencimientoValido(vencimiento: string, hoy: Date): boolean {
  const coincidencia = /^(\d{2})\/(\d{2})$/.exec(vencimiento)
  if (!coincidencia) return false
  const mes = Number(coincidencia[1])
  const anio = 2000 + Number(coincidencia[2])
  if (mes < 1 || mes > 12) return false
  const anioActual = hoy.getFullYear()
  const mesActual = hoy.getMonth() + 1
  const noHaVencido = anio > anioActual || (anio === anioActual && mes >= mesActual)
  return noHaVencido && anio <= anioActual + ANIOS_MAXIMOS_DE_VIGENCIA
}

export function validarTarjeta(datos: DatosTarjeta, hoy: Date): ErroresTarjeta {
  const errores: ErroresTarjeta = {}
  const marca = detectarMarca(datos.numero)

  if (datos.titular.trim().length < 3) {
    errores.titular = 'Escribe el nombre como aparece en la tarjeta.'
  }
  if (soloDigitos(datos.numero).length !== longitudNumero(marca) || !pasaLuhn(datos.numero)) {
    errores.numero = 'Revisa el número de la tarjeta.'
  }
  if (!esVencimientoValido(datos.vencimiento, hoy)) {
    errores.vencimiento = 'Fecha inválida o vencida (MM/AA).'
  }
  if (soloDigitos(datos.cvv).length !== longitudCvv(marca)) {
    errores.cvv = `El código tiene ${longitudCvv(marca)} dígitos.`
  }
  return errores
}

export function tieneErrores(errores: ErroresTarjeta): boolean {
  return Object.keys(errores).length > 0
}

/** En la simulación, esta tarjeta representa un pago que el banco rechaza. */
export function esTarjetaDeRechazo(numero: string): boolean {
  return soloDigitos(numero) === soloDigitos(TARJETA_PRUEBA_RECHAZADA)
}

/** "4242 4242 4242 4242" -> "•••• 4242". */
export function ocultarNumero(numero: string): string {
  return `•••• ${soloDigitos(numero).slice(-4)}`
}