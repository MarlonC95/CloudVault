import { CheckCircle2, FileText, Film, Folder, Image as IconoImagen, Users } from 'lucide-react'

const CARPETAS = ['Proyectos', 'Facturas', 'Fotos']

const ARCHIVOS = [
  { icono: FileText, nombre: 'Informe final.pdf', tamano: '2.4 MB', color: '#DC2626' },
  { icono: IconoImagen, nombre: 'Portada.jpg', tamano: '860 KB', color: '#7C3AED' },
  { icono: Film, nombre: 'Demo del sistema.mp4', tamano: '48 MB', color: '#2563EB' },
]

const MENU = ['Mi Unidad', 'Compartidos', 'Recientes', 'Papelera']

/** Dibujo de la app hecho con HTML (no es una captura), para ilustrar el hero. */
function MaquetaApp() {
  return (
    <div className="position-relative" aria-hidden="true">
      <div className="lp-maqueta">
        <div className="d-flex align-items-center gap-2" style={{ padding: '10px 14px', background: '#F1F5F9', borderBottom: '1px solid #E2E8F0' }}>
          {['#F87171', '#FBBF24', '#34D399'].map((color) => (
            <span key={color} style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
          ))}
          <span className="ms-2" style={{ fontSize: 11, color: '#94A3B8', background: '#fff', borderRadius: 6, padding: '2px 10px' }}>
            cloudvault.app/dashboard
          </span>
        </div>
        <div className="d-flex" style={{ minHeight: 300 }}>
          <div className="d-none d-sm-block" style={{ width: 132, background: '#0F172A', padding: '14px 10px' }}>
            <div style={{ background: '#2563EB', color: '#fff', fontSize: 11, fontWeight: 600, borderRadius: 8, padding: '7px 8px', textAlign: 'center', marginBottom: 12 }}>
              Subir archivo
            </div>
            {MENU.map((opcion, indice) => (
              <div
                key={opcion}
                style={{
                  fontSize: 11,
                  color: indice === 0 ? '#fff' : '#94A3B8',
                  background: indice === 0 ? '#1E293B' : 'transparent',
                  borderRadius: 6,
                  padding: '6px 8px',
                  marginBottom: 2,
                }}
              >
                {opcion}
              </div>
            ))}
            <div style={{ marginTop: 18, fontSize: 10, color: '#94A3B8' }}>Almacenamiento</div>
            <div style={{ height: 5, background: '#1E293B', borderRadius: 3, marginTop: 6 }}>
              <div style={{ width: '38%', height: '100%', background: '#3B82F6', borderRadius: 3 }} />
            </div>
            <div style={{ fontSize: 10, color: '#64748B', marginTop: 4 }}>5.7 GB de 15 GB</div>
          </div>
          <div className="flex-grow-1" style={{ padding: 16, color: '#0F172A' }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Mi Unidad</div>
            <div className="d-flex gap-2 mb-3">
              {CARPETAS.map((carpeta) => (
                <div key={carpeta} className="d-flex align-items-center gap-1 flex-fill" style={{ border: '1px solid #E2E8F0', borderRadius: 8, padding: '7px 8px', fontSize: 11 }}>
                  <Folder size={13} color="#2563EB" fill="#DBEAFE" /> {carpeta}
                </div>
              ))}
            </div>
            {ARCHIVOS.map(({ icono: Icono, nombre, tamano, color }) => (
              <div key={nombre} className="d-flex align-items-center gap-2" style={{ padding: '8px 4px', borderBottom: '1px solid #F1F5F9', fontSize: 11 }}>
                <span className="d-flex align-items-center justify-content-center" style={{ width: 24, height: 24, borderRadius: 6, background: `${color}14` }}>
                  <Icono size={13} color={color} />
                </span>
                <span className="flex-grow-1" style={{ fontWeight: 500 }}>{nombre}</span>
                <span style={{ color: '#94A3B8' }}>{tamano}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="lp-flotante d-flex align-items-center gap-2" style={{ left: -18, bottom: -22 }}>
        <CheckCircle2 size={18} color="#16A34A" />
        <div>
          <div style={{ fontWeight: 700 }}>Subida completada</div>
          <div style={{ color: '#64748B', fontSize: 12 }}>Demo del sistema.mp4</div>
        </div>
      </div>
      <div className="lp-flotante d-none d-md-flex align-items-center gap-2" style={{ right: -14, top: -20, animationDelay: '1.5s' }}>
        <Users size={16} color="#2563EB" />
        <span style={{ fontWeight: 600 }}>3 miembros en tu equipo</span>
      </div>
    </div>
  )
}

export default MaquetaApp