import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Loader2, ShieldCheck } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import TarjetaVisual from '../components/pago/TarjetaVisual'
import FormularioTarjeta from '../components/pago/FormularioTarjeta'
import ResumenPedido from '../components/pago/ResumenPedido'
import AvisoSimulacion from '../components/pago/AvisoSimulacion'
import ResultadoPago from '../components/pago/ResultadoPago'
import { listarPlanes, suscribirPlan } from '../services/planesService'
import { ErrorApi } from '../services/errorApi'
import { formatearFechaCorta } from '../utils/fechas'
import { esTipoFacturacion, formatearUsd, obtenerMontoPlan } from '../utils/planes'
import {
  detectarMarca,
  esTarjetaDeRechazo,
  formatearNumeroTarjeta,
  formatearVencimiento,
  longitudCvv,
  obtenerNombreMarca,
  ocultarNumero,
  soloDigitos,
  tieneErrores,
  validarTarjeta,
} from '../utils/tarjeta'
import { COLOR_MARCA } from '../theme/colores'
import type { Plan, ResultadoSuscripcion, TipoFacturacion } from '../types/planes'
import type { CampoTarjeta, DatosTarjeta, ErroresTarjeta, EtapaPago } from '../types/pago'

const TARJETA_VACIA: DatosTarjeta = { titular: '', numero: '', vencimiento: '', cvv: '' }

/** Pausa breve para que la simulación se sienta como una pasarela real. */
const DEMORA_PROCESAMIENTO_MS = 1600

function esperar(milisegundos: number): Promise<void> {
  return new Promise((resolver) => setTimeout(resolver, milisegundos))
}

/** Da formato a cada campo mientras se escribe. */
function normalizarCampo(campo: CampoTarjeta, valor: string, numeroActual: string): string {
  if (campo === 'numero') return formatearNumeroTarjeta(valor)
  if (campo === 'vencimiento') return formatearVencimiento(valor)
  if (campo === 'cvv') return soloDigitos(valor).slice(0, longitudCvv(detectarMarca(numeroActual)))
  return valor
}

function PagoPage() {
  const [parametros] = useSearchParams()
  const planId = parametros.get('plan')
  const facturacionInicial = parametros.get('facturacion')

  const [plan, setPlan] = useState<Plan | null>(null)
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState('')
  const [facturacion, setFacturacion] = useState<TipoFacturacion>(
    esTipoFacturacion(facturacionInicial) ? facturacionInicial : 'mensual',
  )

  const [datos, setDatos] = useState<DatosTarjeta>(TARJETA_VACIA)
  const [errores, setErrores] = useState<ErroresTarjeta>({})
  const [mostrarReverso, setMostrarReverso] = useState(false)
  const [etapa, setEtapa] = useState<EtapaPago>('formulario')
  const [errorPago, setErrorPago] = useState('')
  const [resultado, setResultado] = useState<ResultadoSuscripcion | null>(null)

  useEffect(() => {
    let cancelado = false
    listarPlanes()
      .then((catalogo) => {
        if (cancelado) return
        const elegido = catalogo.resultados.find((opcion) => opcion.id === planId)
        if (!elegido || elegido.precioMensual <= 0) {
          setErrorCarga('Ese plan no existe o no necesita pago. Elige un plan de pago desde Planes.')
        } else {
          setPlan(elegido)
        }
      })
      .catch((error) => {
        if (!cancelado) setErrorCarga(error instanceof ErrorApi ? error.message : 'No se pudo cargar el plan.')
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [planId])

  function cambiarCampo(campo: CampoTarjeta, valor: string) {
    setDatos((actuales) => {
      const siguientes = { ...actuales, [campo]: normalizarCampo(campo, valor, actuales.numero) }
      // Si cambia la marca (por ejemplo a American Express), el código de seguridad cambia de largo.
      if (campo === 'numero') siguientes.cvv = normalizarCampo('cvv', actuales.cvv, siguientes.numero)
      return siguientes
    })
    setErrores((actuales) => ({ ...actuales, [campo]: undefined }))
    setErrorPago('')
  }

  function usarTarjetaDePrueba(numero: string) {
    setDatos((actuales) => ({
      titular: actuales.titular || 'Usuario de prueba',
      numero: formatearNumeroTarjeta(numero),
      vencimiento: actuales.vencimiento || '12/30',
      cvv: actuales.cvv || '123',
    }))
    setErrores({})
    setErrorPago('')
  }

  async function pagar() {
    if (!plan) return
    const erroresEncontrados = validarTarjeta(datos, new Date())
    setErrores(erroresEncontrados)
    if (tieneErrores(erroresEncontrados)) return

    setEtapa('procesando')
    setErrorPago('')
    await esperar(DEMORA_PROCESAMIENTO_MS)

    if (esTarjetaDeRechazo(datos.numero)) {
      setEtapa('rechazado')
      return
    }

    try {
      // Solo viajan el plan y la facturación; los datos de la tarjeta nunca se envían.
      setResultado(await suscribirPlan(plan.id, facturacion))
      setEtapa('aprobado')
    } catch (error) {
      const mensaje =
        error instanceof ErrorApi && error.codigo === 'CUOTA_EXCEDIDA'
          ? (error.campos.plan_id?.[0] ?? error.message)
          : error instanceof ErrorApi
            ? error.message
            : 'No se pudo completar el pago. Intenta de nuevo.'
      setErrorPago(mensaje)
      setEtapa('formulario')
    }
  }

  function intentarDeNuevo() {
    setDatos((actuales) => ({ ...actuales, numero: '', cvv: '' }))
    setEtapa('formulario')
  }

  const procesando = etapa === 'procesando'
  const marca = detectarMarca(datos.numero)

  function contenido() {
    if (cargando) {
      return (
        <div className="d-flex align-items-center justify-content-center gap-2" style={{ minHeight: 320, color: '#64748B' }}>
          <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> Cargando el plan…
        </div>
      )
    }

    if (errorCarga || !plan) {
      return (
        <ResultadoPago
          aprobado={false}
          titulo="No podemos iniciar el pago"
          mensaje={errorCarga || 'No se encontró el plan.'}
          accionPrincipal={null}
        />
      )
    }

    if (etapa === 'aprobado' && resultado) {
      return (
        <ResultadoPago
          aprobado
          titulo="¡Pago aprobado!"
          mensaje={`Tu plan ${resultado.plan.nombre} ya está activo. Ya puedes usar tu nuevo espacio.`}
          filas={[
            { etiqueta: 'Plan', valor: `${resultado.plan.nombre} · ${plan.almacenamientoLegible}` },
            { etiqueta: 'Facturación', valor: resultado.plan.tipoFacturacion === 'anual' ? 'Anual' : 'Mensual' },
            { etiqueta: 'Total pagado', valor: formatearUsd(obtenerMontoPlan(plan, facturacion)) },
            { etiqueta: 'Tarjeta', valor: `${obtenerNombreMarca(marca)} ${ocultarNumero(datos.numero)}` },
            { etiqueta: 'Próxima renovación', valor: formatearFechaCorta(resultado.renuevaEn) },
          ]}
          accionPrincipal={
            <Link to="/dashboard" className="btn text-white fw-semibold" style={{ background: COLOR_MARCA, borderRadius: 50, padding: '10px 22px' }}>
              Ir a mi unidad
            </Link>
          }
        />
      )
    }

    if (etapa === 'rechazado') {
      return (
        <ResultadoPago
          aprobado={false}
          titulo="Pago rechazado"
          mensaje="El banco simulado rechazó la tarjeta. No se hizo ningún cargo y tu plan actual sigue igual."
          filas={[
            { etiqueta: 'Tarjeta', valor: `${obtenerNombreMarca(marca)} ${ocultarNumero(datos.numero)}` },
            { etiqueta: 'Monto', valor: formatearUsd(obtenerMontoPlan(plan, facturacion)) },
          ]}
          accionPrincipal={
            <button type="button" onClick={intentarDeNuevo} className="btn text-white fw-semibold" style={{ background: COLOR_MARCA, borderRadius: 50, padding: '10px 22px' }}>
              Intentar con otra tarjeta
            </button>
          }
        />
      )
    }

    return (
      <div className="row g-4 align-items-start">
        <div className="col-12 col-lg-7">
          <section style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 18, padding: 24, boxShadow: '0 1px 3px rgba(15,23,42,0.04)' }}>
            <div className="mb-4">
              <TarjetaVisual datos={datos} mostrarReverso={mostrarReverso} />
            </div>
            <form
              noValidate
              onSubmit={(evento) => {
                evento.preventDefault()
                void pagar()
              }}
            >
              <FormularioTarjeta
                datos={datos}
                errores={errores}
                deshabilitado={procesando}
                onCambiar={cambiarCampo}
                onEnfocarCvv={setMostrarReverso}
              />
              {errorPago && (
                <p role="alert" className="small mt-3 mb-0" style={{ color: '#DC2626' }}>
                  {errorPago}
                </p>
              )}
              <button
                type="submit"
                disabled={procesando}
                className="btn w-100 text-white fw-semibold d-flex align-items-center justify-content-center gap-2 mt-4"
                style={{ background: COLOR_MARCA, borderRadius: 50, padding: '13px', fontSize: 15, boxShadow: '0 8px 20px rgba(37,99,235,0.25)' }}
              >
                {procesando ? (
                  <>
                    <Loader2 size={17} style={{ animation: 'spin 1s linear infinite' }} /> Procesando pago…
                  </>
                ) : (
                  <>Pagar {formatearUsd(obtenerMontoPlan(plan, facturacion))}</>
                )}
              </button>
              <p className="d-flex align-items-center justify-content-center gap-1 mt-3 mb-0" style={{ fontSize: 12, color: '#94A3B8' }}>
                <ShieldCheck size={14} /> Pago simulado · los datos de la tarjeta no salen de tu navegador
              </p>
            </form>
          </section>
        </div>

        <div className="col-12 col-lg-5 d-flex flex-column gap-3">
          <ResumenPedido plan={plan} facturacion={facturacion} deshabilitado={procesando} onCambiarFacturacion={setFacturacion} />
          <AvisoSimulacion deshabilitado={procesando} onUsarTarjeta={usarTarjetaDePrueba} />
        </div>
      </div>
    )
  }

  return (
    <DashboardLayout seccionActiva="planes">
      <div style={{ padding: '32px 24px', width: '100%', maxWidth: 1100, margin: '0 auto' }}>
        {etapa === 'formulario' || etapa === 'procesando' ? (
          <header className="mb-4">
            <Link to="/planes" className="d-inline-flex align-items-center gap-1 mb-3 text-decoration-none" style={{ fontSize: 13, fontWeight: 600, color: COLOR_MARCA }}>
              <ArrowLeft size={14} /> Volver a planes
            </Link>
            <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em', marginBottom: 6 }}>Finalizar compra</h1>
            <p className="mb-0" style={{ fontSize: 14, color: '#64748B' }}>Completa los datos de la tarjeta para activar tu nuevo plan.</p>
          </header>
        ) : null}
        {contenido()}
      </div>
    </DashboardLayout>
  )
}

export default PagoPage