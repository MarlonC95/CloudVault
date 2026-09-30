import { MoreVertical, Download } from 'lucide-react'
import { COLOR_MARCA, COLOR_ICONO_FONDO } from '../../theme/colores'
import { obtenerConfiguracionTipoArchivo } from '../../utils/tiposArchivo'
import type { Archivo } from '../../types/archivo'

interface TablaArchivosProps {
  archivos: Archivo[]
  archivoSeleccionadoId: string | null
  onSeleccionarArchivo: (archivo: Archivo) => void
}

function TablaArchivos({ archivos, archivoSeleccionadoId, onSeleccionarArchivo }: TablaArchivosProps) {
  return (
    <div className="bg-white" style={{ border: '1px solid #E2E8F0', borderRadius: '16px', overflow: 'hidden' }}>
      <div
        className="d-flex justify-content-between align-items-center px-4 py-3"
        style={{ borderBottom: '1px solid #E2E8F0' }}
      >
        <span className="fw-semibold small text-uppercase" style={{ color: '#64748B', letterSpacing: '0.04em' }}>
          Todos los archivos
        </span>
        <span className="small text-secondary">Actualizado hace 2 min</span>
      </div>

      <div className="table-responsive">
        <table className="table mb-0 align-middle">
          <thead>
            <tr>
              <th className="small text-uppercase text-secondary border-0 px-4" style={{ fontSize: '11px' }}>
                Nombre
              </th>
              <th
                className="small text-uppercase text-secondary border-0 d-none d-md-table-cell"
                style={{ fontSize: '11px' }}
              >
                Fecha de modificación
              </th>
              <th
                className="small text-uppercase text-secondary border-0 d-none d-md-table-cell"
                style={{ fontSize: '11px' }}
              >
                Tamaño
              </th>
              <th className="small text-uppercase text-secondary border-0 text-end px-4" style={{ fontSize: '11px' }}>
                Acciones
              </th>
            </tr>
          </thead>
          <tbody>
            {archivos.map((archivo) => {
              const configuracion = obtenerConfiguracionTipoArchivo(archivo.tipo)
              const estaSeleccionado = archivo.id === archivoSeleccionadoId

              return (
                <tr
                  key={archivo.id}
                  role="button"
                  onClick={() => onSeleccionarArchivo(archivo)}
                  style={{ backgroundColor: estaSeleccionado ? COLOR_ICONO_FONDO : 'transparent', cursor: 'pointer' }}
                >
                  <td className="px-4">
                    <div className="d-flex align-items-center gap-2">
                      <span
                        className="d-inline-flex align-items-center justify-content-center fw-bold"
                        style={{
                          backgroundColor: configuracion.colorFondo,
                          color: configuracion.colorTexto,
                          borderRadius: '6px',
                          fontSize: '11px',
                          padding: '3px 6px',
                        }}
                      >
                        {configuracion.etiqueta}
                      </span>
                      <span className="fw-medium" style={{ color: '#0F172A' }}>
                        {archivo.nombre}
                      </span>
                      {archivo.esNuevo && (
                        <span
                          style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: COLOR_MARCA }}
                        />
                      )}
                    </div>
                  </td>
                  <td className="text-secondary small d-none d-md-table-cell">{archivo.fechaModificacion}</td>
                  <td className="text-secondary small d-none d-md-table-cell">{archivo.tamano}</td>
                  <td className="text-end px-4">
                    <div className="d-flex justify-content-end gap-2" onClick={(evento) => evento.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn-sm d-flex align-items-center gap-1 fw-semibold"
                        style={{ backgroundColor: COLOR_ICONO_FONDO, color: COLOR_MARCA, borderRadius: '8px' }}
                      >
                        <Download size={14} /> Descargar
                      </button>
                      <button type="button" className="btn btn-sm btn-light border" style={{ borderRadius: '8px' }}>
                        <MoreVertical size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default TablaArchivos