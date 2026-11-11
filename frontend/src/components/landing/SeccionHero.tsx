import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import MaquetaApp from './MaquetaApp'

function SeccionHero() {
  return (
    <header id="inicio" className="lp-hero">
      <div className="lp-contenedor">
        <div className="row g-5 align-items-center">
          <div className="col-12 col-lg-6">
            <h1 className="lp-titulo-hero" style={{ marginTop: 0 }}>
              Tus archivos, seguros y en orden. <span>En la nube.</span>
            </h1>
            <p className="lp-subtitulo-hero mb-4">
              CloudVault es una plataforma de almacenamiento para guardar, organizar y compartir archivos, sola o con tu
              equipo, con control de quién puede ver y editar cada cosa.
            </p>
            <div className="d-flex flex-wrap gap-3 mb-3">
              <Link to="/registro" className="lp-boton lp-boton-primario">
                Empieza gratis <ArrowRight size={17} />
              </Link>
              <a href="#planes" className="lp-boton lp-boton-claro">
                Ver planes
              </a>
            </div>
            <p className="mb-0" style={{ fontSize: 13, color: '#94A3B8' }}>
              15 GB gratis · sin tarjeta · cancela cuando quieras
            </p>
          </div>
          <div className="col-12 col-lg-6">
            <MaquetaApp />
          </div>
        </div>
      </div>
    </header>
  )
}

export default SeccionHero