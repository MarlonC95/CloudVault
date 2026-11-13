import { useEffect, useState } from 'react'
import { X, Download, FileText, Loader2, AlertCircle } from 'lucide-react'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface ModalVistaPreviaProps {
  archivo: Archivo | null
  urlVistaPrevia: string | null
  tipoMime?: string | null
  contenidoTexto?: string | null
  cargando: boolean
  error: string | null
  onCerrar: () => void
  onDescargar: (archivo: Archivo) => void
}

type ModoRenderizado = 'texto' | 'imagen' | 'pdf' | 'video' | 'audio' | 'descarga'

function obtenerModoRenderizado(
  nombre: string,
  tipoMime?: string | null,
  tieneTexto?: boolean,
): ModoRenderizado {
  if (tieneTexto) return 'texto'
  const mime = (tipoMime ?? '').toLowerCase()
  const ext = nombre.includes('.') ? nombre.split('.').pop()?.toLowerCase() ?? '' : ''

  if (mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'].includes(ext)) {
    return 'imagen'
  }
  if (mime === 'application/pdf' || ext === 'pdf') {
    return 'pdf'
  }
  if (mime.startsWith('video/') || ['mp4', 'webm', 'ogg', 'mov'].includes(ext)) {
    return 'video'
  }
  if (mime.startsWith('audio/') || ['mp3', 'wav', 'ogg', 'm4a', 'flac'].includes(ext)) {
    return 'audio'
  }
  if (
    mime.startsWith('text/') ||
    mime === 'application/json' ||
    ['txt', 'md', 'markdown', 'json', 'csv', 'js', 'ts', 'tsx', 'jsx', 'py', 'html', 'css', 'xml', 'log', 'sql'].includes(ext)
  ) {
    return 'texto'
  }
  return 'descarga'
}

function ModalVistaPrevia({
  archivo,
  urlVistaPrevia,
  tipoMime,
  contenidoTexto,
  cargando,
  error,
  onCerrar,
  onDescargar,
}: ModalVistaPreviaProps) {
  const [textoRemoto, setTextoRemoto] = useState<string | null>(null)
  const [cargandoTextoRemoto, setCargandoTextoRemoto] = useState(false)

  useEffect(() => {
    if (!archivo) return
    function manejarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') onCerrar()
    }
    document.addEventListener('keydown', manejarTecla)
    return () => document.removeEventListener('keydown', manejarTecla)
  }, [archivo, onCerrar])

  const modo = archivo
    ? obtenerModoRenderizado(archivo.nombre, tipoMime, contenidoTexto !== null && contenidoTexto !== undefined)
    : 'descarga'

  useEffect(() => {
    setTextoRemoto(null)
    if (!archivo || !urlVistaPrevia || contenidoTexto !== null && contenidoTexto !== undefined) return
    if (modo !== 'texto') return

    let cancelado = false
    setCargandoTextoRemoto(true)
    fetch(urlVistaPrevia)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error('No disponible'))))
      .then((texto) => {
        if (!cancelado) setTextoRemoto(texto)
      })
      .catch(() => {
        if (!cancelado) setTextoRemoto(null)
      })
      .finally(() => {
        if (!cancelado) setCargandoTextoRemoto(false)
      })
    return () => {
      cancelado = true
    }
  }, [archivo, urlVistaPrevia, contenidoTexto, modo])

  if (!archivo) return null

  const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
  const textoFinal = contenidoTexto ?? textoRemoto

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Vista previa de ${archivo.nombre}`}
      onClick={onCerrar}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.72)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        zIndex: 200,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 960,
          height: '85vh',
          background: '#FFFFFF',
          borderRadius: 16,
          boxShadow: '0 25px 60px rgba(15, 23, 42, 0.35)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid #E2E8F0',
        }}
      >
        {/* Cabecera del modal */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '14px 20px',
            borderBottom: '1px solid #E2E8F0',
            background: '#F8FAFC',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                backgroundColor: configuracion.colorFondo,
                color: configuracion.colorTexto,
                borderRadius: 6,
                fontSize: 11,
                padding: '4px 8px',
                flexShrink: 0,
              }}
            >
              {configuracion.etiqueta}
            </span>
            <div style={{ minWidth: 0 }}>
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 700,
                  color: '#0F172A',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {archivo.nombre}
              </p>
              <p style={{ margin: 0, fontSize: 11, color: '#64748B' }}>
                {archivo.tamano} · Modificado {archivo.fechaModificacion}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => onDescargar(archivo)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 12px',
                borderRadius: 8,
                border: '1px solid #2563EB',
                background: '#2563EB',
                color: '#FFFFFF',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Download size={13} />
              Descargar
            </button>
            <button
              type="button"
              onClick={onCerrar}
              aria-label="Cerrar vista previa"
              style={{
                width: 32,
                height: 32,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 8,
                border: '1px solid #E2E8F0',
                background: '#FFFFFF',
                color: '#64748B',
                cursor: 'pointer',
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Cuerpo de la vista previa */}
        <div
          style={{
            flex: 1,
            background: '#0F172A',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'auto',
            position: 'relative',
          }}
        >
          {cargando || cargandoTextoRemoto ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, color: '#E2E8F0' }}>
              <Loader2 size={32} color="#60A5FA" />
              <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>Preparando vista previa segura...</p>
            </div>
          ) : error ? (
            <div
              style={{
                maxWidth: 420,
                background: '#1E293B',
                border: '1px solid #334155',
                borderRadius: 14,
                padding: 28,
                textAlign: 'center',
                color: '#F8FAFC',
              }}
            >
              <AlertCircle size={36} color="#F87171" style={{ marginBottom: 10 }} />
              <p style={{ margin: '0 0 6px', fontSize: 15, fontWeight: 700 }}>No se pudo cargar la vista previa</p>
              <p style={{ margin: '0 0 18px', fontSize: 13, color: '#94A3B8' }}>{error}</p>
              <button
                type="button"
                onClick={() => onDescargar(archivo)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '9px 16px',
                  borderRadius: 8,
                  border: 'none',
                  background: '#2563EB',
                  color: '#FFFFFF',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <Download size={14} />
                Descargar archivo en su lugar
              </button>
            </div>
          ) : modo === 'texto' && textoFinal !== null ? (
            <div
              style={{
                width: '100%',
                height: '100%',
                padding: 28,
                overflow: 'auto',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'flex-start',
              }}
            >
              <div
                style={{
                  width: '100%',
                  maxWidth: 820,
                  background: '#FFFFFF',
                  borderRadius: 12,
                  padding: '28px 32px',
                  boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
                  border: '1px solid #E2E8F0',
                }}
              >
                <pre
                  style={{
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontSize: 13,
                    lineHeight: 1.65,
                    color: '#0F172A',
                  }}
                >
                  {textoFinal || '(Archivo vacío)'}
                </pre>
              </div>
            </div>
          ) : urlVistaPrevia ? (
            modo === 'imagen' ? (
              <img
                src={urlVistaPrevia}
                alt={archivo.nombre}
                style={{
                  maxWidth: '94%',
                  maxHeight: '94%',
                  objectFit: 'contain',
                  borderRadius: 8,
                  boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
                  background: '#FFFFFF',
                }}
              />
            ) : modo === 'pdf' ? (
              <iframe
                src={urlVistaPrevia}
                title={`Vista previa de ${archivo.nombre}`}
                style={{
                  width: '100%',
                  height: '100%',
                  border: 'none',
                  background: '#FFFFFF',
                }}
              />
            ) : modo === 'video' ? (
              <video
                src={urlVistaPrevia}
                controls
                autoPlay
                style={{
                  maxWidth: '94%',
                  maxHeight: '94%',
                  borderRadius: 8,
                  background: '#000',
                }}
              />
            ) : modo === 'audio' ? (
              <div
                style={{
                  background: '#1E293B',
                  border: '1px solid #334155',
                  borderRadius: 16,
                  padding: 32,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 16,
                  minWidth: 340,
                }}
              >
                <FileText size={42} color="#60A5FA" />
                <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#F8FAFC' }}>{archivo.nombre}</p>
                <audio src={urlVistaPrevia} controls autoPlay style={{ width: '100%' }} />
              </div>
            ) : (
              <div
                style={{
                  maxWidth: 440,
                  background: '#1E293B',
                  border: '1px solid #334155',
                  borderRadius: 16,
                  padding: 32,
                  textAlign: 'center',
                  color: '#F8FAFC',
                }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: 14,
                    background: configuracion.colorFondo,
                    color: configuracion.colorTexto,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 800,
                    fontSize: 14,
                    marginBottom: 14,
                  }}
                >
                  {configuracion.etiqueta}
                </div>
                <p style={{ margin: '0 0 6px', fontSize: 16, fontWeight: 700 }}>{archivo.nombre}</p>
                <p style={{ margin: '0 0 20px', fontSize: 13, color: '#94A3B8', lineHeight: 1.5 }}>
                  Este formato ({configuracion.etiqueta}) no tiene visor embebido directo, pero puedes descargarlo con su nombre original.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                  <button
                    type="button"
                    onClick={() => onDescargar(archivo)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '9px 15px',
                      borderRadius: 8,
                      border: 'none',
                      background: '#2563EB',
                      color: '#FFFFFF',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    <Download size={14} />
                    Descargar archivo
                  </button>
                </div>
              </div>
            )
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default ModalVistaPrevia
