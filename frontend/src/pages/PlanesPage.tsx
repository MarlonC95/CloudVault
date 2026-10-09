import { useEffect, useMemo, useState } from 'react'
import { HardDrive, CheckCircle, Check, ChevronRight, X, Loader2 } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import { listarPlanes, obtenerMiPlan, suscribirPlan } from '../services/planesService'
import { ErrorApi } from '../services/errorApi'
import type { Plan, MiPlan, TipoFacturacion, Factura } from '../types/planes'

type EstadoBoton = 'deshabilitado' | 'solido' | 'contorno'

interface PlanCatalogo extends Plan {
  accion: { etiqueta: string; estilo: EstadoBoton }
}

const FILAS_COMPARATIVA_FIJAS: { etiqueta: string; valores: (string | boolean)[] }[] = [
  { etiqueta: 'Usuarios', valores: ['1', '5', 'Ilimitados'] },
  { etiqueta: 'Cifrado', valores: ['Estándar', 'E2E', 'E2E'] },
  { etiqueta: 'Versionado', valores: [false, true, true] },
  { etiqueta: 'API dedicada', valores: [false, false, true] },
  { etiqueta: 'Auditoría', valores: [false, false, true] },
  { etiqueta: 'SLA', valores: ['—', '99.5%', '99.9%'] },
  { etiqueta: 'Soporte', valores: ['Comunidad', '24/7', 'Dedicado'] },
]

const PREGUNTAS_FRECUENTES = [
  { pregunta: '¿Puedo cambiar de plan en cualquier momento?', respuesta: 'Sí. Los cambios se aplican de forma prorrateada al ciclo de facturación vigente.' },
  { pregunta: '¿Qué ocurre con mis archivos al bajar de plan?', respuesta: 'Tus archivos no se eliminan. Tendrás acceso de solo lectura hasta reducir el uso.' },
  { pregunta: '¿Hay descuento para ONGs o educación?', respuesta: 'Ofrecemos un 50% de descuento verificable. Escríbenos a ventas@cloudvault.io.' },
  { pregunta: '¿Dónde están los servidores?', respuesta: 'Centros de datos en Madrid y Fráncfort con réplica en tiempo real (ISO 27001).' },
]

function formatearPrecio(plan: Plan, facturacion: TipoFacturacion): string {
  const monto = facturacion === 'anual' ? plan.precioAnual : plan.precioMensual
  return `$${monto}`
}

function construirAccion(planId: string, planActualId: string): { etiqueta: string; estilo: EstadoBoton } {
  if (planId === planActualId) {
    return planId === 'gratuito'
      ? { etiqueta: 'Plan Actual', estilo: 'deshabilitado' }
      : { etiqueta: 'Suscrito', estilo: 'solido' }
  }
  return { etiqueta: 'Actualizar Plan', estilo: 'contorno' }
}

function PlanesPage() {
  const [facturacion, setFacturacion] = useState<TipoFacturacion>('mensual')
  const [planes, setPlanes] = useState<Plan[]>([])
  const [miPlan, setMiPlan] = useState<MiPlan | null>(null)
  const [facturas] = useState<Factura[]>([])
  const [cargando, setCargando] = useState(true)
  const [errorGeneral, setErrorGeneral] = useState('')
  const [suscribiendoPlanId, setSuscribiendoPlanId] = useState<string | null>(null)

  async function cargarDatos() {
    try {
      const [catalogo, actual] = await Promise.all([listarPlanes(), obtenerMiPlan()])
      setPlanes(catalogo.resultados)
      setMiPlan(actual)
      setFacturacion(actual.plan.tipoFacturacion)
    } catch (error) {
      setErrorGeneral(error instanceof ErrorApi ? error.message : 'No se pudieron cargar los planes.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => {
    let cancelado = false
    Promise.all([listarPlanes(), obtenerMiPlan()])
      .then(([catalogo, actual]) => {
        if (cancelado) return
        setPlanes(catalogo.resultados)
        setMiPlan(actual)
        setFacturacion(actual.plan.tipoFacturacion)
      })
      .catch((error) => {
        if (!cancelado) setErrorGeneral(error instanceof ErrorApi ? error.message : 'No se pudieron cargar los planes.')
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [])

  const planesCatalogo: PlanCatalogo[] = useMemo(() => {
    return planes.map((plan) => ({
      ...plan,
      accion: construirAccion(plan.id, miPlan?.plan.id ?? ''),
    }))
  }, [planes, miPlan])

  const filasComparativa = useMemo(() => {
    const almacenamientos = planesCatalogo.map((plan) => plan.almacenamientoLegible)
    return [
      { etiqueta: 'Almacenamiento', valores: almacenamientos },
      ...FILAS_COMPARATIVA_FIJAS,
    ]
  }, [planesCatalogo])

  async function manejarActualizarPlan(plan: PlanCatalogo) {
    if (plan.id === miPlan?.plan.id) return
    setSuscribiendoPlanId(plan.id)
    setErrorGeneral('')
    try {
      await suscribirPlan(plan.id, facturacion)
      await cargarDatos()
    } catch (error) {
      if (error instanceof ErrorApi && error.codigo === 'CUOTA_EXCEDIDA') {
        setErrorGeneral(error.campos.plan_id?.[0] ?? error.message)
      } else {
        setErrorGeneral(error instanceof ErrorApi ? error.message : 'No se pudo actualizar el plan.')
      }
    } finally {
      setSuscribiendoPlanId(null)
    }
  }


  const almacenamientoUsado = miPlan?.almacenamiento.usadoLegible ?? '—'
  const almacenamientoTotal = miPlan?.almacenamiento.cuotaLegible ?? '—'
  const porcentajeUsado = miPlan?.almacenamiento.porcentajeUsado ?? 0
  const nombrePlanActual = miPlan?.plan.nombre ?? '—'
  const libreTexto = miPlan?.almacenamiento.libreLegible ?? '—'

  return (
    <DashboardLayout seccionActiva="planes">
      <div style={{ padding: '32px 24px', width: '100%' }}>
        {/* Encabezado */}
        <div style={{ textAlign: 'center', marginBottom: 32, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h1 style={{ fontSize: 32, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.02em', marginBottom: 10 }}>
            Planes y Almacenamiento
          </h1>
          <p style={{ fontSize: 16, color: '#64748B', marginBottom: 24, lineHeight: 1.55 }}>
            Escala la capacidad de tu plataforma PaaS según las necesidades de tu equipo.
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
            <div style={{ display: 'inline-flex', background: '#F1F5F9', borderRadius: 9, padding: 3 }}>
              {(['mensual', 'anual'] as const).map((opcion) => (
                <button
                  key={opcion}
                  type="button"
                  onClick={() => setFacturacion(opcion)}
                  disabled={cargando}
                  style={{
                    padding: '8px 20px',
                    borderRadius: 7,
                    border: 'none',
                    background: facturacion === opcion ? '#fff' : 'transparent',
                    color: facturacion === opcion ? '#0F172A' : '#64748B',
                    fontWeight: facturacion === opcion ? 600 : 400,
                    fontSize: 13,
                    cursor: cargando ? 'not-allowed' : 'pointer',
                    boxShadow: facturacion === opcion ? '0 1px 4px rgba(0,0,0,0.09)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  {opcion === 'anual' ? (
                    <>
                      Anual
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#16A34A', background: 'rgba(22,163,74,0.1)', borderRadius: 4, padding: '1px 5px' }}>
                        –20%
                      </span>
                    </>
                  ) : (
                    'Mensual'
                  )}
                </button>
              ))}
            </div>
          </div>

          {errorGeneral && (
            <div className="alert alert-danger" role="alert" style={{ maxWidth: 560, width: '100%', marginBottom: 16 }}>
              {errorGeneral}
            </div>
          )}

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 20,
              background: '#fff',
              border: '1px solid #E2E8F0',
              borderRadius: 12,
              padding: '14px 24px',
              boxShadow: '0 1px 4px rgba(15,23,42,0.04)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <HardDrive size={15} color="#2563EB" strokeWidth={1.9} />
              <span style={{ fontSize: 13, color: '#64748B' }}>Tu consumo actual:</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
                {almacenamientoUsado} / {almacenamientoTotal}
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#2563EB', background: 'rgba(37,99,235,0.08)', borderRadius: 5, padding: '2px 7px' }}>
                {cargando ? 'Cargando…' : nombrePlanActual}
              </span>
            </div>
            <div style={{ width: 140, height: 6, background: '#F1F5F9', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${porcentajeUsado}%`, height: '100%', background: '#2563EB', borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: 12, color: '#94A3B8' }}>{libreTexto} libres</span>
          </div>
        </div>

        {cargando ? (
          <div style={{ textAlign: 'center', padding: '48px 0', color: '#64748B' }}>
            <Loader2 size={32} className="spin" style={{ animation: 'spin 1s linear infinite', marginBottom: 12 }} />
            <p className="mb-0">Cargando planes…</p>
          </div>
        ) : (
          <>
            {/* Tarjetas de precios */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 48, alignItems: 'start' }}>
              {planesCatalogo.map((plan) => (
                <div
                  key={plan.id}
                  style={{
                    background: '#fff',
                    border: `${plan.esPopular ? '2px' : '1px'} solid ${plan.esPopular ? '#2563EB' : '#E2E8F0'}`,
                    borderRadius: 16,
                    padding: 24,
                    position: 'relative',
                    boxShadow: plan.esPopular ? '0 8px 32px rgba(37,99,235,0.12), 0 0 0 4px rgba(37,99,235,0.06)' : '0 1px 4px rgba(15,23,42,0.04)',
                  }}
                >
                  {plan.esPopular && (
                    <div
                      style={{
                        position: 'absolute',
                        top: -14,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        background: '#2563EB',
                        color: '#fff',
                        fontSize: 10,
                        fontWeight: 700,
                        letterSpacing: '0.08em',
                        padding: '5px 14px',
                        borderRadius: 20,
                        whiteSpace: 'nowrap',
                        boxShadow: '0 2px 8px rgba(37,99,235,0.35)',
                      }}
                    >
                      MÁS POPULAR
                    </div>
                  )}

                  <div style={{ marginBottom: 16, marginTop: plan.esPopular ? 8 : 0 }}>
                    <p style={{ fontSize: 20, fontWeight: 700, color: '#0F172A', margin: 0, letterSpacing: '-0.01em' }}>{plan.nombre}</p>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 20 }}>
                    <span style={{ fontSize: 32, fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', lineHeight: 1 }}>
                      {formatearPrecio(plan, facturacion)}
                    </span>
                    <span style={{ fontSize: 13, color: '#94A3B8', fontWeight: 400 }}>
                      {facturacion === 'anual' ? '/ año' : '/ mes'}
                    </span>
                  </div>

                  {plan.accion.estilo === 'deshabilitado' && (
                    <button
                      type="button"
                      disabled
                      style={{
                        width: '100%',
                        height: 44,
                        background: '#F1F5F9',
                        color: '#64748B',
                        border: '1px solid #E2E8F0',
                        borderRadius: 10,
                        fontWeight: 600,
                        fontSize: 14,
                        cursor: 'not-allowed',
                        marginBottom: 22,
                      }}
                    >
                      {plan.accion.etiqueta}
                    </button>
                  )}
                  {plan.accion.estilo === 'solido' && (
                    <button
                      type="button"
                      style={{
                        width: '100%',
                        height: 44,
                        background: '#2563EB',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 10,
                        fontWeight: 600,
                        fontSize: 14,
                        cursor: 'default',
                        marginBottom: 22,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 7,
                      }}
                    >
                      <CheckCircle size={15} strokeWidth={2} />
                      {plan.accion.etiqueta}
                    </button>
                  )}
                  {plan.accion.estilo === 'contorno' && (
                    <button
                      type="button"
                      onClick={() => manejarActualizarPlan(plan)}
                      disabled={suscribiendoPlanId === plan.id}
                      style={{
                        width: '100%',
                        height: 44,
                        background: 'transparent',
                        color: '#2563EB',
                        border: '2px solid #2563EB',
                        borderRadius: 10,
                        fontWeight: 600,
                        fontSize: 14,
                        cursor: suscribiendoPlanId === plan.id ? 'wait' : 'pointer',
                        marginBottom: 22,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                      }}
                    >
                      {suscribiendoPlanId === plan.id ? (
                        <>
                          <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
                          Procesando…
                        </>
                      ) : (
                        <>
                          {plan.accion.etiqueta}
                          <ChevronRight size={15} strokeWidth={2.3} />
                        </>
                      )}
                    </button>
                  )}

                  <div style={{ height: 1, background: '#F1F5F9', marginBottom: 18 }} />

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {[`${plan.almacenamientoLegible} almacenamiento`, ...plan.caracteristicas].map((caracteristica) => (
                      <div key={caracteristica} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div
                          style={{
                            width: 18,
                            height: 18,
                            borderRadius: '50%',
                            background: plan.esPopular ? 'rgba(37,99,235,0.1)' : 'rgba(22,163,74,0.08)',
                            border: `1px solid ${plan.esPopular ? 'rgba(37,99,235,0.2)' : 'rgba(22,163,74,0.2)'}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <Check size={10} strokeWidth={2.8} color={plan.esPopular ? '#2563EB' : '#16A34A'} />
                        </div>
                        <span style={{ fontSize: 13, color: '#374151', lineHeight: 1.4 }}>{caracteristica}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Comparativa detallada */}
            <div style={{ marginBottom: 44 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 16, letterSpacing: '-0.01em' }}>
                Comparativa detallada
              </h2>
              <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', padding: '0 20px' }}>
                  {['Característica', 'Gratuito', 'Pro PaaS', 'Empresarial'].map((encabezado, indice) => (
                    <div key={encabezado} style={{ padding: '12px 0', fontSize: 12, fontWeight: 700, color: indice === 2 ? '#2563EB' : '#64748B', letterSpacing: '0.03em' }}>
                      {encabezado}
                    </div>
                  ))}
                </div>

                {filasComparativa.map((fila, indiceFila) => (
                  <div
                    key={fila.etiqueta}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '2fr 1fr 1fr 1fr',
                      padding: '0 20px',
                      borderBottom: indiceFila < filasComparativa.length - 1 ? '1px solid #F1F5F9' : 'none',
                    }}
                  >
                    <div style={{ padding: '12px 0', fontSize: 13, fontWeight: 500, color: '#374151' }}>{fila.etiqueta}</div>
                    {fila.valores.map((valor, indiceColumna) => (
                      <div key={indiceColumna} style={{ padding: '12px 0', display: 'flex', alignItems: 'center' }}>
                        {typeof valor === 'boolean' ? (
                          valor ? (
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: '50%',
                                background: indiceColumna === 1 ? 'rgba(37,99,235,0.1)' : 'rgba(22,163,74,0.08)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              <Check size={11} strokeWidth={2.8} color={indiceColumna === 1 ? '#2563EB' : '#16A34A'} />
                            </div>
                          ) : (
                            <div style={{ width: 20, height: 20, borderRadius: '50%', background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              <X size={10} strokeWidth={2.5} color="#CBD5E1" />
                            </div>
                          )
                        ) : (
                          <span style={{ fontSize: 13, color: valor === '—' ? '#CBD5E1' : indiceColumna === 1 ? '#2563EB' : '#374151', fontWeight: indiceColumna === 1 ? 600 : 400 }}>
                            {valor}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Historial de facturas */}
            {facturas.length > 0 && (
              <div style={{ marginBottom: 44 }}>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 16, letterSpacing: '-0.01em' }}>
                  Historial de facturas
                </h2>
                <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
                  {facturas.map((factura) => (
                    <div
                      key={factura.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '14px 20px',
                        borderBottom: '1px solid #F1F5F9',
                      }}
                    >
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0 }}>{factura.id}</p>
                        <p style={{ fontSize: 12, color: '#64748B', margin: '2px 0 0' }}>
                          {factura.periodoInicio} – {factura.periodoFin}
                        </p>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: factura.estado === 'pagada' ? '#16A34A' : '#0F172A',
                            background: factura.estado === 'pagada' ? 'rgba(22,163,74,0.08)' : '#F1F5F9',
                            borderRadius: 20,
                            padding: '2px 8px',
                          }}
                        >
                          {factura.estado}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
                          {factura.monto} {factura.moneda}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Preguntas frecuentes */}
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0F172A', marginBottom: 16, letterSpacing: '-0.01em' }}>
                Preguntas frecuentes
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                {PREGUNTAS_FRECUENTES.map((item) => (
                  <div key={item.pregunta} style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 20px' }}>
                    <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', marginBottom: 6, lineHeight: 1.4 }}>{item.pregunta}</p>
                    <p style={{ fontSize: 12, color: '#64748B', lineHeight: 1.65 }}>{item.respuesta}</p>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}

export default PlanesPage
