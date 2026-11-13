import { Link } from 'react-router-dom'
import { Cloud, ArrowRight } from 'lucide-react'
import { obtenerSesion } from '../../services/authService'

const ENLACES = [
  { destino: '#caracteristicas', etiqueta: 'Características' },
  { destino: '#como-funciona', etiqueta: 'Cómo funciona' },
  { destino: '#planes', etiqueta: 'Planes' },
  { destino: '#preguntas', etiqueta: 'Preguntas' },
]

function BarraNavegacion() {
  const sesion = obtenerSesion()

  return (
    <nav className="lp-nav" aria-label="Principal">
      <div className="lp-contenedor d-flex align-items-center justify-content-between" style={{ height: 64 }}>
        <a href="#inicio" className="d-flex align-items-center gap-2 text-decoration-none text-white">
          <Cloud size={26} color="#60A5FA" />
          <span className="fw-bold fs-5">CloudVault</span>
        </a>
        <div className="d-none d-md-flex align-items-center gap-4">
          {ENLACES.map((enlace) => (
            <a key={enlace.destino} href={enlace.destino} className="lp-enlace">
              {enlace.etiqueta}
            </a>
          ))}
        </div>
        <div className="d-flex align-items-center gap-2">
          {sesion ? (
            <Link to="/dashboard" className="lp-boton lp-boton-primario lp-boton-pequeno d-inline-flex align-items-center gap-1">
              Ir a mi unidad <ArrowRight size={15} />
            </Link>
          ) : (
            <>
              <Link to="/login" className="lp-enlace d-none d-sm-inline px-2" style={{ color: '#E2E8F0', fontSize: 14, fontWeight: 600, textDecoration: 'none' }}>
                Iniciar sesión
              </Link>
              <Link to="/registro" className="lp-boton lp-boton-primario lp-boton-pequeno">
                Crear cuenta
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}

export default BarraNavegacion