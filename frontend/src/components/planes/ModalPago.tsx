import { useEffect, useState } from 'react'
import { X, CreditCard, Plus, Loader2, Lock } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO } from '../../theme/colores'
import { useOrganizacion } from '../../context/organizacionesContexto'
import { convertirEnErrorApi } from '../../services/errorApi'
import { actualizarTarjeta, eliminarTarjeta, guardarTarjeta, listarTarjetas } from '../../services/planesService'
import type { DatosTarjeta, Tarjeta, TipoTarjeta } from '../../types/planes'

const MAX_TARJETAS = 2
const ANIO_ACTUAL = new Date().getFullYear()
const ANIOS = Array.from({ length: 16 }, (_, i) => ANIO_ACTUAL + i)
const MESES = Array.from({ length: 12 }, (_, i) => i + 1)
const ESTILO_CAMPO = { backgroundColor: COLOR_ICONO_FONDO, border: 'none', borderRadius: '10px', padding: '10px 14px' }

const FORMULARIO_VACIO: DatosTarjeta = { titular: '', numero: '', cvv: '', mesExpiracion: 1, anioExpiracion: ANIO_ACTUAL, tipo: 'credito' }

interface ModalPagoProps {
  /** Sin `cobro` el modal solo gestiona las tarjetas guardadas. */
  cobro?: { concepto: string; monto: number }
  onCerrar: () => void
  onPagar?: (tarjetaId: string) => Promise<void>
}

function mensajeDeError(causa: unknown): string {
  const error = convertirEnErrorApi(causa)
  return Object.values(error.campos).flat().join(' ') || error.message
}

/** Amex (34/37) tiene 15 dígitos y CVV de 4; el resto, 16 y 3 (mismas reglas que el backend). */
const esAmex = (numero: string) => /^3[47]/.test(numero)

/** Limita el número a su largo y lo agrupa en bloques de 4 mientras se escribe. */
function formatearNumero(valor: string): string {
  const digitos = valor.replace(/\D/g, '')
  return digitos.slice(0, esAmex(digitos) ? 15 : 16).replace(/(\d{4})(?=\d)/g, '$1 ')
}

function ModalPago({ cobro, onCerrar, onPagar }: ModalPagoProps) {
  const { organizacion, ejecutar } = useOrganizacion()
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [seleccionada, setSeleccionada] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  // null: lista; 'nueva': alta; Tarjeta: actualizar esa tarjeta.
  const [editando, setEditando] = useState<'nueva' | Tarjeta | null>(null)
  const [formulario, setFormulario] = useState<DatosTarjeta>(FORMULARIO_VACIO)
  const [procesando, setProcesando] = useState(false)
  const [error, setError] = useState('')

  function aplicarTarjetas(lista: Tarjeta[]) {
    setTarjetas(lista)
    setSeleccionada((actual) =>
      lista.some((t) => t.id === actual) ? actual : (lista.find((t) => t.predeterminada) ?? lista[0])?.id ?? null)
    if (lista.length === 0) abrirFormulario('nueva')
  }

  useEffect(() => {
    let cancelado = false
    listarTarjetas(organizacion.id)
      .then((lista) => { if (!cancelado) aplicarTarjetas(lista) })
      .catch((causa) => { if (!cancelado) setError(mensajeDeError(causa)) })
      .finally(() => { if (!cancelado) setCargando(false) })
    return () => { cancelado = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- aplicarTarjetas solo usa setters estables
  }, [organizacion.id])

  function abrirFormulario(objetivo: 'nueva' | Tarjeta) {
    setError('')
    setEditando(objetivo)
    setFormulario(objetivo === 'nueva'
      ? FORMULARIO_VACIO
      : { titular: objetivo.titular, numero: '', cvv: '', mesExpiracion: objetivo.mesExpiracion, anioExpiracion: objetivo.anioExpiracion, tipo: objetivo.tipo })
  }

  async function operar(accion: () => Promise<void>) {
    setProcesando(true)
    setError('')
    try {
      await accion()
    } catch (causa) {
      setError(mensajeDeError(causa))
    } finally {
      setProcesando(false)
    }
  }

  const recargar = async () => aplicarTarjetas(await listarTarjetas(organizacion.id))

  const guardar = () => operar(async () => {
    const datos = { ...formulario, numero: formulario.numero.replace(/\s/g, '') }
    if (editando === 'nueva') {
      const nueva = await ejecutar(() => guardarTarjeta(datos, organizacion.id))
      setSeleccionada(nueva.id)
    } else if (editando) {
      // Número y CVV solo se envían si se reemplaza la tarjeta.
      const cambios: Partial<DatosTarjeta> = { ...datos }
      if (!datos.numero) {
        delete cambios.numero
        delete cambios.cvv
      }
      await ejecutar(() => actualizarTarjeta(editando.id, cambios, organizacion.id))
    }
    setEditando(null)
    await recargar()
  })

  const pagar = () => operar(async () => {
    if (seleccionada && onPagar) await onPagar(seleccionada)
  })

  const campo = <K extends keyof DatosTarjeta>(clave: K, valor: DatosTarjeta[K]) =>
    setFormulario((actual) => ({ ...actual, [clave]: valor }))
  const largoCvv = esAmex(formulario.numero) ? 4 : 3

  return (
    <div
      className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
      style={{ backgroundColor: 'rgba(15,23,42,0.5)', zIndex: 1060 }}
      onClick={() => !procesando && onCerrar()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tituloModalPago"
        className="bg-white w-100"
        style={{ maxWidth: '480px', borderRadius: '20px', padding: '24px', margin: '0 16px', maxHeight: '92vh', overflowY: 'auto' }}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="d-flex justify-content-between align-items-center mb-1">
          <h5 id="tituloModalPago" className="fw-bold mb-0">{cobro ? 'Confirmar pago' : 'Métodos de pago'}</h5>
          <button type="button" className="btn btn-sm p-1" onClick={onCerrar} disabled={procesando} aria-label="Cerrar">
            <X size={20} />
          </button>
        </div>
        <p className="small text-muted mb-3">
          Pago simulado: no se realiza ningún cargo real. Solo se guardan la marca, los 4 últimos dígitos y la fecha de vencimiento.
        </p>

        {cobro && (
          <div className="d-flex justify-content-between align-items-center mb-3 p-3" style={{ background: '#F8FAFC', borderRadius: 12 }}>
            <span className="small fw-semibold">{cobro.concepto}</span>
            <span className="fw-bold" style={{ fontSize: 20 }}>${cobro.monto} USD</span>
          </div>
        )}

        {cargando ? (
          <div className="text-center py-4 text-muted"><Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} /></div>
        ) : editando ? (
          <form onSubmit={(evento) => { evento.preventDefault(); void guardar() }}>
            <p className="small fw-semibold mb-2">
              {editando === 'nueva' ? 'Nueva tarjeta' : `Actualizar ${editando.marca.toUpperCase()} •••• ${editando.ultimos4}`}
            </p>
            <div className="d-flex gap-3 mb-2">
              {(['credito', 'debito'] as TipoTarjeta[]).map((tipo) => (
                <label key={tipo} className="small d-flex align-items-center gap-1">
                  <input type="radio" name="tipoTarjeta" checked={formulario.tipo === tipo} onChange={() => campo('tipo', tipo)} />
                  {tipo === 'credito' ? 'Crédito' : 'Débito'}
                </label>
              ))}
            </div>
            <label htmlFor="titularTarjeta" className="form-label small fw-semibold mb-1">Titular</label>
            <input id="titularTarjeta" className="form-control mb-2" style={ESTILO_CAMPO} autoComplete="cc-name" required
              value={formulario.titular} onChange={(e) => campo('titular', e.target.value)} placeholder="Como aparece en la tarjeta" />
            <label htmlFor="numeroTarjeta" className="form-label small fw-semibold mb-1">
              Número {editando !== 'nueva' && <span className="text-muted fw-normal">(déjalo vacío para conservar el actual)</span>}
            </label>
            <input id="numeroTarjeta" className="form-control mb-2" style={ESTILO_CAMPO} inputMode="numeric" autoComplete="cc-number"
              required={editando === 'nueva'} value={formulario.numero}
              onChange={(e) => {
                const numero = formatearNumero(e.target.value)
                setFormulario((actual) => ({ ...actual, numero, cvv: actual.cvv.slice(0, esAmex(numero) ? 4 : 3) }))
              }}
              placeholder="4242 4242 4242 4242" />
            <div className="d-flex gap-2 mb-3">
              <div className="flex-fill">
                <label htmlFor="mesTarjeta" className="form-label small fw-semibold mb-1">Mes</label>
                <select id="mesTarjeta" className="form-select" style={ESTILO_CAMPO} autoComplete="cc-exp-month"
                  value={formulario.mesExpiracion} onChange={(e) => campo('mesExpiracion', Number(e.target.value))}>
                  {MESES.map((mes) => <option key={mes} value={mes}>{String(mes).padStart(2, '0')}</option>)}
                </select>
              </div>
              <div className="flex-fill">
                <label htmlFor="anioTarjeta" className="form-label small fw-semibold mb-1">Año</label>
                <select id="anioTarjeta" className="form-select" style={ESTILO_CAMPO} autoComplete="cc-exp-year"
                  value={formulario.anioExpiracion} onChange={(e) => campo('anioExpiracion', Number(e.target.value))}>
                  {ANIOS.map((anio) => <option key={anio} value={anio}>{anio}</option>)}
                </select>
              </div>
              <div style={{ width: 90 }}>
                <label htmlFor="cvvTarjeta" className="form-label small fw-semibold mb-1">CVV</label>
                <input id="cvvTarjeta" type="password" className="form-control" style={ESTILO_CAMPO} inputMode="numeric" autoComplete="cc-csc"
                  minLength={largoCvv} maxLength={largoCvv} required={editando === 'nueva' || formulario.numero !== ''}
                  value={formulario.cvv}
                  onChange={(e) => campo('cvv', e.target.value.replace(/\D/g, '').slice(0, largoCvv))} />
              </div>
            </div>
            {error && <p role="alert" className="small text-danger">{error}</p>}
            <div className="d-flex gap-2">
              {tarjetas.length > 0 && (
                <button type="button" className="btn btn-light flex-fill" style={{ borderRadius: 50 }} onClick={() => setEditando(null)} disabled={procesando}>
                  Cancelar
                </button>
              )}
              <button type="submit" className="btn text-white fw-semibold flex-fill" style={{ backgroundColor: COLOR_MARCA, borderRadius: 50 }} disabled={procesando}>
                {procesando ? 'Guardando…' : 'Guardar tarjeta'}
              </button>
            </div>
          </form>
        ) : (
          <>
            <div className="d-flex flex-column gap-2 mb-3">
              {tarjetas.map((tarjeta) => (
                <div key={tarjeta.id} className="p-3" style={{ border: `2px solid ${cobro && seleccionada === tarjeta.id ? COLOR_MARCA : '#E2E8F0'}`, borderRadius: 12 }}>
                  <label className="d-flex align-items-center gap-2 mb-1" style={{ cursor: cobro ? 'pointer' : 'default' }}>
                    {cobro && (
                      <input type="radio" name="tarjetaPago" checked={seleccionada === tarjeta.id} onChange={() => setSeleccionada(tarjeta.id)} />
                    )}
                    <CreditCard size={18} color={COLOR_MARCA} />
                    <span className="fw-semibold small">{tarjeta.marca.toUpperCase()} •••• {tarjeta.ultimos4}</span>
                    <span className="small text-muted">
                      {tarjeta.tipo === 'credito' ? 'Crédito' : 'Débito'} · {String(tarjeta.mesExpiracion).padStart(2, '0')}/{String(tarjeta.anioExpiracion).slice(-2)}
                    </span>
                    {tarjeta.predeterminada && <span className="badge text-bg-light ms-auto">Predeterminada</span>}
                  </label>
                  <div className="d-flex gap-3 small">
                    <button type="button" className="btn btn-link btn-sm p-0" onClick={() => abrirFormulario(tarjeta)} disabled={procesando}>Actualizar</button>
                    {!tarjeta.predeterminada && (
                      <button type="button" className="btn btn-link btn-sm p-0" disabled={procesando}
                        onClick={() => operar(async () => { await ejecutar(() => actualizarTarjeta(tarjeta.id, { predeterminada: true }, organizacion.id)); await recargar() })}>
                        Usar como predeterminada
                      </button>
                    )}
                    <button type="button" className="btn btn-link btn-sm p-0 text-danger" disabled={procesando}
                      onClick={() => operar(async () => { await ejecutar(() => eliminarTarjeta(tarjeta.id, organizacion.id)); await recargar() })}>
                      Eliminar
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {tarjetas.length < MAX_TARJETAS ? (
              <button type="button" className="btn btn-light w-100 d-flex justify-content-center align-items-center gap-2 mb-3" style={{ borderRadius: 50 }}
                onClick={() => abrirFormulario('nueva')} disabled={procesando}>
                <Plus size={16} /> Agregar tarjeta
              </button>
            ) : (
              <p className="small text-muted mb-3">Puedes guardar hasta {MAX_TARJETAS} tarjetas. Actualiza o elimina una para cambiarla.</p>
            )}
            {error && <p role="alert" className="small text-danger">{error}</p>}
            {cobro && (
              <button type="button" onClick={pagar} disabled={!seleccionada || procesando}
                className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold"
                style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px', padding: '10px' }}>
                {procesando ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Procesando pago…</> : <><Lock size={16} /> Pagar ${cobro.monto} USD</>}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default ModalPago
