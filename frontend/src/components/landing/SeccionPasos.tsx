import { PASOS } from '../../data/landing'

function SeccionPasos() {
  return (
    <section id="como-funciona" className="lp-seccion lp-seccion-gris">
      <div className="lp-contenedor">
        <div className="text-center mb-5">
          <span className="lp-etiqueta">Cómo funciona</span>
          <h2 className="lp-titulo-seccion">Empieza en tres pasos</h2>
        </div>
        <ol className="row g-4 list-unstyled mb-0">
          {PASOS.map((paso, indice) => (
            <li key={paso.titulo} className="col-12 col-md-4 text-center">
              <div className="lp-numero-paso">{indice + 1}</div>
              <h3 style={{ fontSize: 19, fontWeight: 700, marginBottom: 8 }}>{paso.titulo}</h3>
              <p className="mx-auto mb-0" style={{ color: '#64748B', lineHeight: 1.6, maxWidth: 300 }}>{paso.descripcion}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

export default SeccionPasos