import { useState } from 'react'
import { HardDrive, CheckCircle, Check, ChevronRight, X } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'

type NivelPlan = 'gratuito' | 'pro' | 'empresarial'
type TipoFacturacion = 'mensual' | 'anual'

interface PlanCatalogo {
  id: NivelPlan
  nombre: string
  precioMensual: number
  precioAnual: number
  almacenamientoLegible: string
  esPopular: boolean
  caracteristicas: string[]
  accion: { etiqueta: string; estilo: 'deshabilitado' | 'solido' | 'contorno' }
}

// TODO(backend): reemplazar por GET /api/v1/planes/ (contrato sección 10.1).
// Fuente de verdad del almacenamiento y precio: tabla "planes" de la base de datos.
const PLANES: PlanCatalogo[] = [
  {
    id: 'gratuito',
    nombre: 'Gratuito',
    precioMensual: 0,
    precioAnual: 0,
    almacenamientoLegible: '15 GB',
    esPopular: false,
    caracteristicas: ['1 Usuario', 'Cifrado estándar', 'Soporte por comunidad'],
    accion: { etiqueta: 'Plan Actual', estilo: 'deshabilitado' },
  },
  {
    id: 'pro',
    nombre: 'Pro PaaS',
    precioMensual: 29,
    precioAnual: 278,
    almacenamientoLegible: '100 GB',
    esPopular: true,
    caracteristicas: ['Hasta 5 Usuarios', 'Cifrado de extremo a extremo', 'Versionado de archivos', 'Soporte 24/7'],
    accion: { etiqueta: 'Suscrito', estilo: 'solido' },
  },
  {
    id: 'empresarial',
    nombre: 'Empresarial',
    precioMensual: 99,
    precioAnual: 950,
    almacenamientoLegible: '1 TB',
    esPopular: false,
    caracteristicas: ['Usuarios ilimitados', 'Logs de auditoría avanzada', 'API dedicada', 'SLA del 99.9%'],
    accion: { etiqueta: 'Actualizar Plan', estilo: 'contorno' },
  },
]

const FILAS_COMPARATIVA: { etiqueta: string; valores: (string | boolean)[] }[] = [
  { etiqueta: 'Almacenamiento', valores: PLANES.map((plan) => plan.almacenamientoLegible) },
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

function PlanesPage() {
  const [facturacion, setFacturacion] = useState<TipoFacturacion>('mensual')

  // TODO(backend): reemplazar por GET /api/v1/unidad/resumen/ (contrato sección 3.11)
  const almacenamientoUsado = 45
  const almacenamientoTotal = 100
  const porcentajeUsado = (almacenamientoUsado / almacenamientoTotal) * 100

  function obtenerPrecio(plan: PlanCatalogo): string {
    const monto = facturacion === 'anual' ? plan.precioAnual : plan.precioMensual
    return `$${monto}`
  }

  function manejarActualizarPlan(plan: PlanCatalogo) {
    // TODO(backend): POST /api/v1/mi-plan/suscribir/ con { plan_id: plan.id, tipo_facturacion: facturacion }
    // Si responde 409 CUOTA_EXCEDIDA (downgrade con más uso que el nuevo límite), mostrar el error al usuario.
    alert(`Pendiente de conectar: suscribirse a ${plan.nombre} (${facturacion})`)
  }

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
                  style={{
                    padding: '8px 20px',
                    borderRadius: 7,
                    border: 'none',
                    background: facturacion === opcion ? '#fff' : 'transparent',
                    color: facturacion === opcion ? '#0F172A' : '#64748B',
                    fontWeight: facturacion === opcion ? 600 : 400,
                    fontSize: 13,
                    cursor: 'pointer',
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
                {almacenamientoUsado} GB / {almacenamientoTotal} GB
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#2563EB', background: 'rgba(37,99,235,0.08)', borderRadius: 5, padding: '2px 7px' }}>
                Plan Pro
              </span>
            </div>
            <div style={{ width: 140, height: 6, background: '#F1F5F9', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${porcentajeUsado}%`, height: '100%', background: '#2563EB', borderRadius: 3 }} />
            </div>
            <span style={{ fontSize: 12, color: '#94A3B8' }}>{almacenamientoTotal - almacenamientoUsado} GB libres</span>
          </div>
        </div>

        {/* Tarjetas de precios */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 48, alignItems: 'start' }}>
          {PLANES.map((plan) => (
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
                  {obtenerPrecio(plan)}
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
                  style={{
                    width: '100%',
                    height: 44,
                    background: 'transparent',
                    color: '#2563EB',
                    border: '2px solid #2563EB',
                    borderRadius: 10,
                    fontWeight: 600,
                    fontSize: 14,
                    cursor: 'pointer',
                    marginBottom: 22,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                  }}
                >
                  {plan.accion.etiqueta}
                  <ChevronRight size={15} strokeWidth={2.3} />
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

            {FILAS_COMPARATIVA.map((fila, indiceFila) => (
              <div
                key={fila.etiqueta}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 1fr 1fr',
                  padding: '0 20px',
                  borderBottom: indiceFila < FILAS_COMPARATIVA.length - 1 ? '1px solid #F1F5F9' : 'none',
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
      </div>
    </DashboardLayout>
  )
}

export default PlanesPage