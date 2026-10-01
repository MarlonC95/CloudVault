import { Download, Users, Trash2, Shield, AlertTriangle, HardDrive, FileText, Clock, User } from 'lucide-react'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface PanelDetalleArchivoProps {
  archivo: Archivo | null
}

function PanelDetalleArchivo({ archivo }: PanelDetalleArchivoProps) {
  if (!archivo) return null

  const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
  const Icono = configuracion.Icono

  const filas = [
    { etiqueta: 'Tamaño', valor: archivo.tamano, icono: <HardDrive size={12} strokeWidth={1.8} color="#94A3B8" /> },
    { etiqueta: 'Tipo', valor: configuracion.etiqueta, icono: <FileText size={12} strokeWidth={1.8} color="#94A3B8" /> },
    { etiqueta: 'Modificado', valor: archivo.fechaModificacion, icono: <Clock size={12} strokeWidth={1.8} color="#94A3B8" /> },
    { etiqueta: 'Propietario', valor: archivo.propietario, icono: <User size={12} strokeWidth={1.8} color="#94A3B8" /> },
  ]

  return (
    <div
      style={{
        width: 280,
        flexShrink: 0,
        background: '#fff',
        border: '1px solid #E2E8F0',
        borderRadius: 12,
      }}
    >
      <div
        style={{
          background: '#F8FAFC',
          borderBottom: '1px solid #F1F5F9',
          padding: '24px 0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <Icono size={48} color={configuracion.colorTexto} />
        <span
          style={{
            fontWeight: 700,
            backgroundColor: configuracion.colorFondo,
            color: configuracion.colorTexto,
            borderRadius: 6,
            fontSize: 11,
            padding: '2px 8px',
          }}
        >
          {configuracion.etiqueta}
        </span>
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', margin: 0, wordBreak: 'break-word', lineHeight: 1.4 }}>
          {archivo.nombre}
        </p>
      </div>

      <div style={{ padding: '14px 16px' }}>
        {filas.map((fila) => (
          <div key={fila.etiqueta} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
            <div style={{ marginTop: 2, flexShrink: 0 }}>{fila.icono}</div>
            <div>
              <p style={{ fontSize: 10, color: '#94A3B8', margin: 0 }}>{fila.etiqueta}</p>
              <p style={{ fontSize: 12, fontWeight: 500, color: '#0F172A', margin: '1px 0 0' }}>{fila.valor}</p>
            </div>
          </div>
        ))}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 10px',
            borderRadius: 7,
            background: archivo.cifrado ? 'rgba(22,163,74,0.06)' : 'rgba(217,119,6,0.06)',
            border: `1px solid ${archivo.cifrado ? 'rgba(22,163,74,0.2)' : 'rgba(217,119,6,0.2)'}`,
            marginBottom: 14,
          }}
        >
          {archivo.cifrado ? (
            <>
              <Shield size={12} strokeWidth={1.9} color="#16A34A" />
              <span style={{ fontSize: 11, color: '#16A34A', fontWeight: 500 }}>Cifrado activo</span>
            </>
          ) : (
            <>
              <AlertTriangle size={12} strokeWidth={1.9} color="#D97706" />
              <span style={{ fontSize: 11, color: '#D97706', fontWeight: 500 }}>Sin cifrado</span>
            </>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <button
            type="button"
            style={{
              width: '100%',
              background: '#2563EB',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '9px 0',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <Download size={13} strokeWidth={2.2} />
            Descargar
          </button>
          <button
            type="button"
            style={{
              width: '100%',
              background: '#F8FAFC',
              color: '#374151',
              border: '1px solid #E2E8F0',
              borderRadius: 8,
              padding: '8px 0',
              fontWeight: 500,
              fontSize: 13,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <Users size={13} strokeWidth={1.9} />
            Compartir
          </button>
          <button
            type="button"
            style={{
              width: '100%',
              background: '#FEF2F2',
              color: '#DC2626',
              border: '1px solid rgba(220,38,38,0.15)',
              borderRadius: 8,
              padding: '8px 0',
              fontWeight: 500,
              fontSize: 13,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <Trash2 size={13} strokeWidth={1.9} />
            Eliminar
          </button>
        </div>
      </div>
    </div>
  )
}

export default PanelDetalleArchivo