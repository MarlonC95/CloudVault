import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Check, ChevronRight, Clock, Folder, HardDrive, RotateCcw, Trash2 } from 'lucide-react'
import { useArchivos } from '../context/archivosContexto'
import { obtenerConfiguracionTipoArchivo } from '../utils/tiposArchivo'
import {
  DIAS_RETENCION_PAPELERA,
  calcularDiasRestantes,
  calcularTamanoTotalLegible,
  formatearFechaEliminacion,
  obtenerColoresDiasRestantes,
} from '../utils/papelera'
import { COLOR_MARCA, COLOR_NAVY } from '../theme/colores'
import DashboardLayout from '../components/layout/DashboardLayout'

const COLUMNAS_TABLA = '40px minmax(0, 2fr) minmax(0, 1.2fr) minmax(0, 1.1fr) minmax(0, 1.2fr) minmax(0, 1.3fr)'
const COLOR_PELIGRO = '#DC2626'

const ESTILO_BOTON_BARRA: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 13px',
  background: '#FEF2F2',
  border: '1px solid #FCA5A5',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 600,
  color: COLOR_PELIGRO,
}

function pluralizar(cantidad: number, singular: string, plural: string): string {
  return cantidad === 1 ? singular : plural
}

interface CasillaProps {
  marcada: boolean
  color: string
  onCambiar: () => void
  etiqueta: string
}

function Casilla({ marcada, color, onCambiar, etiqueta }: CasillaProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={marcada}
      aria-label={etiqueta}
      onClick={onCambiar}
      style={{
        width: 16,
        height: 16,
        padding: 0,
        borderRadius: 4,
        border: `1.5px solid ${marcada ? color : '#CBD5E1'}`,
        background: marcada ? color : '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        boxSizing: 'border-box',
      }}
    >
      {marcada && <Check size={9} color="#fff" strokeWidth={3} />}
    </button>
  )
}

function PapeleraPage() {
  const navegar = useNavigate()
  const { archivos, carpetas, restaurarArchivos, eliminarDefinitivamente } = useArchivos()

  const [idsSeleccionados, setIdsSeleccionados] = useState<string[]>([])
  const [idsPorEliminar, setIdsPorEliminar] = useState<string[] | null>(null)
  const [idFilaResaltada, setIdFilaResaltada] = useState<string | null>(null)

  const archivosEnPapelera = archivos.filter((archivo) => archivo.enPapelera)
  const seleccionados = idsSeleccionados.filter((id) => archivosEnPapelera.some((archivo) => archivo.id === id))
  const estanTodosSeleccionados = archivosEnPapelera.length > 0 && seleccionados.length === archivosEnPapelera.length
  const papeleraVacia = archivosEnPapelera.length === 0

  const diasHastaPrimerVencimiento = papeleraVacia
    ? null
    : Math.min(...archivosEnPapelera.map((archivo) => calcularDiasRestantes(archivo.eliminadoEn)))

  const tarjetasResumen = [
    {
      etiqueta: 'Archivos en papelera',
      valor: String(archivosEnPapelera.length),
      icono: <Trash2 size={17} color="#64748B" strokeWidth={1.8} />,
    },
    {
      etiqueta: 'Espacio ocupado',
      valor: calcularTamanoTotalLegible(archivosEnPapelera),
      icono: <HardDrive size={17} color="#64748B" strokeWidth={1.8} />,
    },
    {
      etiqueta: 'Próximo en expirar',
      valor:
        diasHastaPrimerVencimiento === null
          ? '—'
          : `${diasHastaPrimerVencimiento} ${pluralizar(diasHastaPrimerVencimiento, 'día', 'días')}`,
      icono: <Clock size={17} color="#D97706" strokeWidth={1.8} />,
    },
  ]

  function alternarSeleccion(archivoId: string) {
    setIdsSeleccionados((anteriores) =>
      anteriores.includes(archivoId) ? anteriores.filter((id) => id !== archivoId) : [...anteriores, archivoId]
    )
  }

  function alternarSeleccionTotal() {
    setIdsSeleccionados(estanTodosSeleccionados ? [] : archivosEnPapelera.map((archivo) => archivo.id))
  }

  function restaurar(ids: string[]) {
    restaurarArchivos(ids)
    setIdsSeleccionados((anteriores) => anteriores.filter((id) => !ids.includes(id)))
  }

  function confirmarEliminacion() {
    if (!idsPorEliminar) return
    eliminarDefinitivamente(idsPorEliminar)
    setIdsSeleccionados((anteriores) => anteriores.filter((id) => !idsPorEliminar.includes(id)))
    setIdsPorEliminar(null)
  }

  function obtenerNombreUbicacion(carpetaId: string | null): string {
    return carpetas.find((carpeta) => carpeta.id === carpetaId)?.nombre ?? 'Mi Unidad'
  }

  return (
    <DashboardLayout seccionActiva="papelera">
      <div style={{ padding: 32 }}>
        {/* Encabezado */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: COLOR_NAVY, letterSpacing: '-0.015em', marginBottom: 4 }}>
              Papelera de reciclaje
            </h1>
            <p style={{ fontSize: 14, color: '#64748B', margin: 0 }}>Gestiona tus archivos eliminados recientemente.</p>
          </div>

          <button
            type="button"
            disabled={papeleraVacia}
            onClick={() => setIdsPorEliminar(archivosEnPapelera.map((archivo) => archivo.id))}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              height: 38,
              padding: '0 16px',
              background: papeleraVacia ? '#F8FAFC' : '#FEF2F2',
              color: papeleraVacia ? '#CBD5E1' : COLOR_PELIGRO,
              border: `1px solid ${papeleraVacia ? '#E2E8F0' : '#FCA5A5'}`,
              borderRadius: 10,
              cursor: papeleraVacia ? 'not-allowed' : 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Trash2 size={14} strokeWidth={2} />
            Vaciar papelera
          </button>
        </div>

        {/* Aviso de retención */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            background: '#FEF3C7',
            border: '1px solid #FDE68A',
            borderRadius: 12,
            padding: '12px 16px',
            marginBottom: 20,
          }}
        >
          <AlertTriangle size={16} color="#D97706" strokeWidth={2} style={{ flexShrink: 0 }} />
          <p style={{ fontSize: 13, color: '#D97706', fontWeight: 500, margin: 0 }}>
            Los elementos en la papelera se eliminarán permanentemente después de{' '}
            <strong>{DIAS_RETENCION_PAPELERA} días</strong>.
          </p>
        </div>

        {/* Resumen */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
          {tarjetasResumen.map((tarjeta) => (
            <div
              key={tarjeta.etiqueta}
              style={{
                background: '#fff',
                border: '1px solid #E2E8F0',
                borderRadius: 12,
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              {tarjeta.icono}
              <div>
                <p style={{ fontSize: 20, fontWeight: 700, color: COLOR_NAVY, margin: 0, lineHeight: 1.2 }}>
                  {tarjeta.valor}
                </p>
                <p style={{ fontSize: 11, color: '#94A3B8', margin: '3px 0 0' }}>{tarjeta.etiqueta}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Barra de acciones sobre la selección */}
        {seleccionados.length > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              background: 'rgba(37,99,235,0.04)',
              border: '1px solid rgba(37,99,235,0.15)',
              borderRadius: 12,
              padding: '10px 16px',
              marginBottom: 12,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 500, color: COLOR_MARCA }}>
              {seleccionados.length} {pluralizar(seleccionados.length, 'elemento seleccionado', 'elementos seleccionados')}
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={() => restaurar(seleccionados)}
                style={{ ...ESTILO_BOTON_BARRA, background: '#fff', border: '1px solid #E2E8F0', color: COLOR_MARCA }}
              >
                <RotateCcw size={13} strokeWidth={2} />
                Restaurar selección
              </button>
              <button type="button" onClick={() => setIdsPorEliminar(seleccionados)} style={ESTILO_BOTON_BARRA}>
                <Trash2 size={13} strokeWidth={2} />
                Eliminar selección
              </button>
            </div>
          </div>
        )}

        {/* Confirmación de borrado permanente */}
        {idsPorEliminar !== null && (
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 14,
              background: '#FEF2F2',
              border: '1px solid #FCA5A5',
              borderRadius: 12,
              padding: '16px 20px',
              marginBottom: 16,
            }}
          >
            <AlertTriangle size={18} color={COLOR_PELIGRO} strokeWidth={2} style={{ flexShrink: 0, marginTop: 1 }} />
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: COLOR_PELIGRO, margin: '0 0 2px' }}>
                Esta acción es irreversible
              </p>
              <p style={{ fontSize: 12, color: '#64748B', margin: 0 }}>
                Se {pluralizar(idsPorEliminar.length, 'eliminará', 'eliminarán')} permanentemente{' '}
                {idsPorEliminar.length} {pluralizar(idsPorEliminar.length, 'archivo', 'archivos')}.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <button
                type="button"
                onClick={confirmarEliminacion}
                style={{
                  background: COLOR_PELIGRO,
                  color: '#fff',
                  border: 'none',
                  borderRadius: 10,
                  padding: '8px 16px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Confirmar
              </button>
              <button
                type="button"
                onClick={() => setIdsPorEliminar(null)}
                style={{
                  background: '#fff',
                  color: '#64748B',
                  border: '1px solid #E2E8F0',
                  borderRadius: 10,
                  padding: '8px 14px',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Tabla o estado vacío */}
        {papeleraVacia ? (
          <div
            style={{
              background: '#fff',
              border: '1px solid #E2E8F0',
              borderRadius: 14,
              padding: '72px 0',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                background: '#F1F5F9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 14px',
              }}
            >
              <Trash2 size={24} color="#CBD5E1" strokeWidth={1.5} />
            </div>
            <p style={{ fontSize: 15, fontWeight: 600, color: '#94A3B8', marginBottom: 6 }}>La papelera está vacía</p>
            <p style={{ fontSize: 13, color: '#CBD5E1', margin: 0 }}>
              Los archivos eliminados aparecerán aquí antes de ser borrados permanentemente
            </p>
          </div>
        ) : (
          <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 14, overflow: 'hidden' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: COLUMNAS_TABLA,
                padding: '0 20px',
                background: '#F8FAFC',
                borderBottom: '1px solid #E2E8F0',
                alignItems: 'center',
              }}
            >
              <div style={{ padding: '11px 0' }}>
                <Casilla
                  marcada={estanTodosSeleccionados}
                  color={COLOR_MARCA}
                  onCambiar={alternarSeleccionTotal}
                  etiqueta="Seleccionar todos"
                />
              </div>
              {['Nombre', 'Ubicación original', 'Fecha de eliminación', 'Tiempo restante', 'Acciones'].map((titulo) => (
                <div
                  key={titulo}
                  style={{ padding: '11px 0', fontSize: 11, fontWeight: 600, color: '#64748B', letterSpacing: '0.04em' }}
                >
                  {titulo}
                </div>
              ))}
            </div>

            {archivosEnPapelera.map((archivo, indice) => {
              const estaSeleccionado = seleccionados.includes(archivo.id)
              const diasRestantes = calcularDiasRestantes(archivo.eliminadoEn)
              const coloresDias = obtenerColoresDiasRestantes(diasRestantes)
              const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
              const Icono = configuracion.Icono
              const esUltimaFila = indice === archivosEnPapelera.length - 1

              let fondoFila = 'transparent'
              if (estaSeleccionado) fondoFila = 'rgba(220,38,38,0.03)'
              else if (idFilaResaltada === archivo.id) fondoFila = '#F8FAFC'

              return (
                <div
                  key={archivo.id}
                  onMouseEnter={() => setIdFilaResaltada(archivo.id)}
                  onMouseLeave={() => setIdFilaResaltada(null)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: COLUMNAS_TABLA,
                    padding: '0 20px',
                    borderBottom: esUltimaFila ? 'none' : '1px solid #F1F5F9',
                    borderLeft: estaSeleccionado ? `3px solid ${COLOR_PELIGRO}` : '3px solid transparent',
                    background: fondoFila,
                    alignItems: 'center',
                  }}
                >
                  <div style={{ padding: '14px 0' }}>
                    <Casilla
                      marcada={estaSeleccionado}
                      color={COLOR_PELIGRO}
                      onCambiar={() => alternarSeleccion(archivo.id)}
                      etiqueta={`Seleccionar ${archivo.nombre}`}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 0', minWidth: 0, opacity: 0.85 }}>
                    <Icono size={18} strokeWidth={1.7} color={configuracion.colorTexto} style={{ flexShrink: 0 }} />
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: COLOR_NAVY,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {archivo.nombre}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Folder size={13} strokeWidth={1.8} color="#94A3B8" />
                    <span style={{ fontSize: 12, color: '#64748B' }}>{obtenerNombreUbicacion(archivo.carpetaId)}</span>
                  </div>

                  <div style={{ fontSize: 12, color: '#64748B' }}>{formatearFechaEliminacion(archivo.eliminadoEn)}</div>

                  <div>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        fontSize: 11,
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                        color: coloresDias.texto,
                        background: coloresDias.fondo,
                        border: `1px solid ${coloresDias.borde}`,
                        borderRadius: 8,
                        padding: '3px 9px',
                      }}
                    >
                      <Clock size={11} strokeWidth={2.2} />
                      {diasRestantes} {pluralizar(diasRestantes, 'día restante', 'días restantes')}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => restaurar([archivo.id])}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '6px 11px',
                        background: 'transparent',
                        border: '1px solid rgba(37,99,235,0.2)',
                        borderRadius: 8,
                        cursor: 'pointer',
                        fontSize: 12,
                        fontWeight: 600,
                        color: COLOR_MARCA,
                      }}
                    >
                      <RotateCcw size={12} strokeWidth={2.2} />
                      Restaurar
                    </button>
                    <button
                      type="button"
                      onClick={() => setIdsPorEliminar([archivo.id])}
                      title="Eliminar permanentemente"
                      aria-label={`Eliminar ${archivo.nombre} permanentemente`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 30,
                        height: 30,
                        background: 'transparent',
                        border: '1px solid rgba(220,38,38,0.2)',
                        borderRadius: 8,
                        cursor: 'pointer',
                        color: COLOR_PELIGRO,
                      }}
                    >
                      <Trash2 size={13} strokeWidth={2} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 32 }}>
          <button
            type="button"
            onClick={() => navegar('/planes')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: COLOR_MARCA,
              color: '#fff',
              border: 'none',
              borderRadius: 10,
              padding: '10px 20px',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Ver planes
            <ChevronRight size={15} strokeWidth={2.2} />
          </button>
        </div>
      </div>
    </DashboardLayout>
  )
}

export default PapeleraPage