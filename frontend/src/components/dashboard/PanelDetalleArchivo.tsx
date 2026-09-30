import { Shield, Download } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface PanelDetalleArchivoProps {
  archivo: Archivo | null
}

function FilaDetalle({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="mb-3">
      <div className="small text-secondary">{etiqueta}</div>
      <div className="fw-medium" style={{ color: '#0F172A' }}>
        {valor}
      </div>
    </div>
  )
}

function PanelDetalleArchivo({ archivo }: PanelDetalleArchivoProps) {
  if (!archivo) {
    return (
      <div
        className="d-none d-xl-flex align-items-center justify-content-center text-center bg-white h-100"
        style={{ border: '1px solid #E2E8F0', borderRadius: '16px', padding: '32px', color: '#94A3B8' }}
      >
        Selecciona un archivo para ver sus detalles.
      </div>
    )
  }

  const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
  const Icono = configuracion.Icono

  return (
    <div
      className="d-none d-xl-flex flex-column bg-white h-100"
      style={{ border: '1px solid #E2E8F0', borderRadius: '16px', padding: '24px' }}
    >
      <div className="d-flex flex-column align-items-center text-center mb-4">
        <div
          className="d-flex align-items-center justify-content-center mb-2"
          style={{ width: '64px', height: '64px', backgroundColor: configuracion.colorFondo, borderRadius: '16px' }}
        >
          <Icono size={28} color={configuracion.colorTexto} />
        </div>
        <span
          className="fw-bold"
          style={{
            backgroundColor: configuracion.colorFondo,
            color: configuracion.colorTexto,
            borderRadius: '6px',
            fontSize: '11px',
            padding: '2px 8px',
          }}
        >
          {configuracion.etiqueta}
        </span>
      </div>

      <h6 className="fw-bold text-break mb-4">{archivo.nombre}</h6>

      <FilaDetalle etiqueta="Tamaño" valor={archivo.tamano} />
      <FilaDetalle etiqueta="Tipo" valor={configuracion.etiqueta} />
      <FilaDetalle etiqueta="Modificado" valor={archivo.fechaModificacion} />
      <FilaDetalle etiqueta="Propietario" valor={archivo.propietario} />

      {archivo.cifrado && (
        <div
          className="d-flex align-items-center gap-2 mb-4 fw-medium small"
          style={{ backgroundColor: '#DCFCE7', color: '#15803D', borderRadius: '10px', padding: '10px 12px' }}
        >
          <Shield size={16} /> Cifrado activo (AES-256)
        </div>
      )}

      <button
        type="button"
        className="btn w-100 d-flex justify-content-center align-items-center gap-2 text-white fw-semibold mt-auto"
        style={{ backgroundColor: COLOR_MARCA, borderRadius: '50px', padding: '10px' }}
      >
        <Download size={18} /> Descargar
      </button>
    </div>
  )
}

export default PanelDetalleArchivo