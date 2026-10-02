import { useState } from 'react'
import { Search, ChevronDown, Check } from 'lucide-react'
import type { RangoFecha, RangoTamano } from '../../utils/filtrosArchivos'
import type { TipoArchivo } from '../../types/archivo'

type FiltroTipo = TipoArchivo | 'todos'

interface BuscadorArchivosProps {
  valorBusqueda: string
  onCambiarBusqueda: (valor: string) => void
  filtroTipo: FiltroTipo
  onCambiarFiltroTipo: (valor: FiltroTipo) => void
  filtroFecha: RangoFecha
  onCambiarFiltroFecha: (valor: RangoFecha) => void
  filtroTamano: RangoTamano
  onCambiarFiltroTamano: (valor: RangoTamano) => void
}

const OPCIONES_TIPO: { valor: FiltroTipo; etiqueta: string }[] = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'pdf', etiqueta: 'PDF' },
  { valor: 'zip', etiqueta: 'ZIP' },
  { valor: 'png', etiqueta: 'Imágenes' },
  { valor: 'js', etiqueta: 'Código' },
  { valor: 'xlsx', etiqueta: 'Hojas de cálculo' },
  { valor: 'mp4', etiqueta: 'Video' },
]

const OPCIONES_FECHA: { valor: RangoFecha; etiqueta: string }[] = [
  { valor: 'cualquiera', etiqueta: 'Cualquier fecha' },
  { valor: 'recientes', etiqueta: 'Últimas 48 horas' },
  { valor: 'este-mes', etiqueta: 'Este mes' },
  { valor: 'anteriores', etiqueta: 'Más antiguos' },
]

const OPCIONES_TAMANO: { valor: RangoTamano; etiqueta: string }[] = [
  { valor: 'cualquiera', etiqueta: 'Cualquier tamaño' },
  { valor: 'pequeno', etiqueta: 'Menos de 1 MB' },
  { valor: 'mediano', etiqueta: '1 MB - 100 MB' },
  { valor: 'grande', etiqueta: 'Más de 100 MB' },
]

function BuscadorArchivos({
  valorBusqueda,
  onCambiarBusqueda,
  filtroTipo,
  onCambiarFiltroTipo,
  filtroFecha,
  onCambiarFiltroFecha,
  filtroTamano,
  onCambiarFiltroTamano,
}: BuscadorArchivosProps) {
  const [enfocado, setEnfocado] = useState(false)
  const [menuAbierto, setMenuAbierto] = useState<'tipo' | 'fecha' | 'tamano' | null>(null)

  function FiltroDropdown<T extends string>({
    etiquetaBase,
    nombreMenu,
    opciones,
    valorActual,
    onCambiar,
  }: {
    etiquetaBase: string
    nombreMenu: 'tipo' | 'fecha' | 'tamano'
    opciones: { valor: T; etiqueta: string }[]
    valorActual: T
    onCambiar: (valor: T) => void
  }) {
    const estaAbierto = menuAbierto === nombreMenu
    const opcionActual = opciones.find((o) => o.valor === valorActual)
    const hayFiltroActivo = valorActual !== opciones[0].valor

    return (
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <button
          type="button"
          onClick={() => setMenuAbierto(estaAbierto ? null : nombreMenu)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '9px 13px',
            background: hayFiltroActivo ? '#EFF6FF' : '#fff',
            border: `1.5px solid ${hayFiltroActivo ? '#BFDBFE' : '#E2E8F0'}`,
            borderRadius: 14,
            fontSize: 13,
            fontWeight: 500,
            color: hayFiltroActivo ? '#2563EB' : '#374151',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {hayFiltroActivo ? opcionActual?.etiqueta : etiquetaBase}
          <ChevronDown size={13} color={hayFiltroActivo ? '#2563EB' : '#94A3B8'} strokeWidth={2} />
        </button>

        {estaAbierto && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              background: '#fff',
              border: '1px solid #E2E8F0',
              borderRadius: 12,
              boxShadow: '0 4px 16px rgba(15,23,42,0.10)',
              zIndex: 60,
              minWidth: 190,
              overflow: 'hidden',
            }}
          >
            {opciones.map((opcion) => (
              <button
                key={opcion.valor}
                type="button"
                onClick={() => {
                  onCambiar(opcion.valor)
                  setMenuAbierto(null)
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '10px 14px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  color: '#374151',
                  textAlign: 'left',
                }}
              >
                {opcion.etiqueta}
                {opcion.valor === valorActual && <Check size={14} color="#2563EB" />}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
        <div
          style={{
            position: 'absolute',
            left: 13,
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            display: 'flex',
          }}
        >
          <Search size={15} strokeWidth={1.9} color={enfocado ? '#2563EB' : '#94A3B8'} />
        </div>
        <input
          value={valorBusqueda}
          onChange={(evento) => onCambiarBusqueda(evento.target.value)}
          onFocus={() => setEnfocado(true)}
          onBlur={() => setEnfocado(false)}
          placeholder="Buscar archivos o carpetas..."
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '10px 14px 10px 38px',
            fontSize: 13,
            color: '#0F172A',
            background: '#fff',
            border: `1.5px solid ${enfocado ? '#2563EB' : '#E2E8F0'}`,
            borderRadius: 14,
            outline: 'none',
          }}
        />
      </div>

      <FiltroDropdown
        etiquetaBase="Tipo"
        nombreMenu="tipo"
        opciones={OPCIONES_TIPO}
        valorActual={filtroTipo}
        onCambiar={onCambiarFiltroTipo}
      />
      <FiltroDropdown
        etiquetaBase="Fecha"
        nombreMenu="fecha"
        opciones={OPCIONES_FECHA}
        valorActual={filtroFecha}
        onCambiar={onCambiarFiltroFecha}
      />
      <FiltroDropdown
        etiquetaBase="Tamaño"
        nombreMenu="tamano"
        opciones={OPCIONES_TAMANO}
        valorActual={filtroTamano}
        onCambiar={onCambiarFiltroTamano}
      />
    </div>
  )
}

export default BuscadorArchivos