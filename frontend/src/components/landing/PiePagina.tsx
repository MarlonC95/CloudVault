import { Link } from 'react-router-dom'
import { ArrowRight, Cloud } from 'lucide-react'

const EQUIPO = ['German Archila', 'Daniel Cifuentes', 'Mily Santay', 'Marlon Celis']

function PiePagina() {
  return (
    <>
      <section className="lp-seccion" style={{ paddingTop: 24 }}>
        <div className="lp-contenedor">
          <div className="lp-cta">
            <h2 style={{ fontSize: 'clamp(26px, 4vw, 38px)', fontWeight: 700, letterSpacing: '-0.02em' }}>
              ¿Listo para ordenar tus archivos?
            </h2>
            <p className="mx-auto mb-4" style={{ color: '#DBEAFE', fontSize: 17, maxWidth: 520 }}>
              Crea tu cuenta gratis y sube tu primer archivo en menos de un minuto.
            </p>
            <Link to="/registro" className="lp-boton" style={{ background: '#fff', color: '#1D4ED8' }}>
              Crear cuenta gratis <ArrowRight size={17} />
            </Link>
          </div>
        </div>
      </section>

      <footer className="lp-pie">
        <div className="lp-contenedor">
          <div className="row g-4 align-items-start">
            <div className="col-12 col-md-6">
              <div className="d-flex align-items-center gap-2 mb-2 text-white">
                <Cloud size={22} color="#60A5FA" />
                <span className="fw-bold">CloudVault</span>
              </div>
              <p className="mb-0" style={{ maxWidth: 380 }}>
                Proyecto académico de Ingeniería de Software I, Universidad Rafael Landívar.
              </p>
            </div>
            <div className="col-6 col-md-3">
              <div className="text-white fw-semibold mb-2">Equipo</div>
              <ul className="list-unstyled mb-0 d-flex flex-column gap-1">
                {EQUIPO.map((integrante) => (
                  <li key={integrante}>{integrante}</li>
                ))}
              </ul>
            </div>
            <div className="col-6 col-md-3">
              <div className="text-white fw-semibold mb-2">Cuenta</div>
              <ul className="list-unstyled mb-0 d-flex flex-column gap-1">
                <li><Link to="/login">Iniciar sesión</Link></li>
                <li><Link to="/registro">Crear cuenta</Link></li>
                <li><a href="#planes">Planes</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-4 pt-3" style={{ borderTop: '1px solid #1E293B', fontSize: 13 }}>
            © 2026 CloudVault · Proyecto académico, sin fines comerciales.
          </div>
        </div>
      </footer>
    </>
  )
}

export default PiePagina