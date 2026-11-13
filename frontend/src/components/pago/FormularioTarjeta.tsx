import type { CSSProperties, ReactNode } from 'react'
import { Calendar, CreditCard, Lock, User } from 'lucide-react'
import type { CampoTarjeta, DatosTarjeta, ErroresTarjeta } from '../../types/pago'
import { detectarMarca, longitudCvv } from '../../utils/tarjeta'
import { COLOR_ICONO_FONDO, COLOR_MARCA } from '../../theme/colores'

interface FormularioTarjetaProps {
  datos: DatosTarjeta
  errores: ErroresTarjeta
  deshabilitado: boolean
  onCambiar: (campo: CampoTarjeta, valor: string) => void
  onEnfocarCvv: (enfocado: boolean) => void
}

const ESTILO_CAMPO: CSSProperties = {
  backgroundColor: COLOR_ICONO_FONDO,
  border: '1.5px solid transparent',
  borderRadius: 12,
  padding: '11px 14px 11px 40px',
  fontSize: 14,
}

interface CampoProps {
  id: CampoTarjeta
  etiqueta: string
  icono: ReactNode
  error?: string
  children: ReactNode
}

function Campo({ id, etiqueta, icono, error, children }: CampoProps) {
  return (
    <div>
      <label htmlFor={id} className="form-label small fw-semibold mb-1" style={{ color: '#334155' }}>
        {etiqueta}
      </label>
      <div className="position-relative">
        <span style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', color: COLOR_MARCA, display: 'flex' }}>
          {icono}
        </span>
        {children}
      </div>
      {error && (
        <p id={`${id}-error`} className="small mb-0 mt-1" style={{ color: '#DC2626' }}>
          {error}
        </p>
      )}
    </div>
  )
}

function estiloConError(error?: string): CSSProperties {
  return error ? { ...ESTILO_CAMPO, borderColor: '#FCA5A5', backgroundColor: '#FEF2F2' } : ESTILO_CAMPO
}

/** Campos de la tarjeta. autoComplete="off" evita que el navegador rellene una tarjeta real guardada. */
function FormularioTarjeta({ datos, errores, deshabilitado, onCambiar, onEnfocarCvv }: FormularioTarjetaProps) {
  const digitosCvv = longitudCvv(detectarMarca(datos.numero))

  return (
    <div className="d-flex flex-column gap-3">
      <Campo id="titular" etiqueta="Nombre en la tarjeta" icono={<User size={16} />} error={errores.titular}>
        <input
          id="titular"
          className="form-control"
          style={estiloConError(errores.titular)}
          placeholder="Como aparece en la tarjeta"
          autoComplete="off"
          maxLength={60}
          value={datos.titular}
          disabled={deshabilitado}
          aria-invalid={Boolean(errores.titular)}
          aria-describedby={errores.titular ? 'titular-error' : undefined}
          onChange={(evento) => onCambiar('titular', evento.target.value)}
        />
      </Campo>

      <Campo id="numero" etiqueta="Número de tarjeta" icono={<CreditCard size={16} />} error={errores.numero}>
        <input
          id="numero"
          className="form-control"
          style={{ ...estiloConError(errores.numero), fontFamily: 'monospace', letterSpacing: '0.06em' }}
          placeholder="0000 0000 0000 0000"
          inputMode="numeric"
          autoComplete="off"
          value={datos.numero}
          disabled={deshabilitado}
          aria-invalid={Boolean(errores.numero)}
          aria-describedby={errores.numero ? 'numero-error' : undefined}
          onChange={(evento) => onCambiar('numero', evento.target.value)}
        />
      </Campo>

      <div className="row g-3">
        <div className="col-6">
          <Campo id="vencimiento" etiqueta="Vencimiento" icono={<Calendar size={16} />} error={errores.vencimiento}>
            <input
              id="vencimiento"
              className="form-control"
              style={{ ...estiloConError(errores.vencimiento), fontFamily: 'monospace' }}
              placeholder="MM/AA"
              inputMode="numeric"
              autoComplete="off"
              value={datos.vencimiento}
              disabled={deshabilitado}
              aria-invalid={Boolean(errores.vencimiento)}
              aria-describedby={errores.vencimiento ? 'vencimiento-error' : undefined}
              onChange={(evento) => onCambiar('vencimiento', evento.target.value)}
            />
          </Campo>
        </div>
        <div className="col-6">
          <Campo id="cvv" etiqueta="Código de seguridad" icono={<Lock size={16} />} error={errores.cvv}>
            <input
              id="cvv"
              className="form-control"
              style={{ ...estiloConError(errores.cvv), fontFamily: 'monospace' }}
              placeholder={'•'.repeat(digitosCvv)}
              inputMode="numeric"
              autoComplete="off"
              type="password"
              value={datos.cvv}
              disabled={deshabilitado}
              aria-invalid={Boolean(errores.cvv)}
              aria-describedby={errores.cvv ? 'cvv-error' : undefined}
              onFocus={() => onEnfocarCvv(true)}
              onBlur={() => onEnfocarCvv(false)}
              onChange={(evento) => onCambiar('cvv', evento.target.value)}
            />
          </Campo>
        </div>
      </div>
    </div>
  )
}

export default FormularioTarjeta