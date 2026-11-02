import { useState } from 'react'
import { Upload } from 'lucide-react'
import { COLOR_MARCA } from '../../theme/colores'
import { subirArchivo } from '../../services/archivosService'
import { convertirEnErrorApi } from '../../services/errorApi'
import ModalSubirArchivo from '../dashboard/ModalSubirArchivo'

interface SubirAquiProps {
  carpetaId: string
  onSubido: () => void
}

/** Botón y modal para subir archivos a una carpeta compartida con permiso de editor. */
function SubirAqui({ carpetaId, onSubido }: SubirAquiProps) {
  const [abierto, setAbierto] = useState(false)
  const [estado, setEstado] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function subir(archivos: File[]) {
    setAbierto(false)
    setError(null)
    try {
      for (const [i, archivo] of archivos.entries()) {
        setEstado(`Subiendo ${i + 1} de ${archivos.length}: ${archivo.name}…`)
        await subirArchivo(archivo, carpetaId)
      }
    } catch (causa) {
      setError(convertirEnErrorApi(causa).message)
    } finally {
      setEstado(null)
      onSubido()
    }
  }

  return (
    <>
      <button
        type="button"
        className="btn btn-sm text-white d-flex align-items-center gap-1"
        style={{ backgroundColor: COLOR_MARCA }}
        disabled={estado !== null}
        onClick={() => setAbierto(true)}
      >
        <Upload size={16} /> Subir aquí
      </button>
      {estado && <p role="status" className="small text-secondary mb-0">{estado}</p>}
      {error && <p role="alert" className="small text-danger mb-0">{error}</p>}
      <ModalSubirArchivo visible={abierto} onCerrar={() => setAbierto(false)} onConfirmarSubida={subir} />
    </>
  )
}

export default SubirAqui
