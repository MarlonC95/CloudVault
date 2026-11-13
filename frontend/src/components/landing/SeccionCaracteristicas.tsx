import { CARACTERISTICAS } from '../../data/landing'

function SeccionCaracteristicas() {
  return (
    <section id="caracteristicas" className="lp-seccion">
      <div className="lp-contenedor">
        <div className="text-center mb-5">
          <span className="lp-etiqueta">Características</span>
          <h2 className="lp-titulo-seccion">Todo lo que necesitas para tus archivos</h2>
          <p className="lp-texto-seccion">Pensado para personas y equipos que quieren su información en un solo lugar, sin complicarse.</p>
        </div>
        <div className="row g-4">
          {CARACTERISTICAS.map(({ icono: Icono, titulo, descripcion }) => (
            <div key={titulo} className="col-12 col-md-6 col-lg-4">
              <article className="lp-tarjeta">
                <div className="lp-icono">
                  <Icono size={22} />
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{titulo}</h3>
                <p className="mb-0" style={{ color: '#64748B', lineHeight: 1.6 }}>{descripcion}</p>
              </article>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default SeccionCaracteristicas