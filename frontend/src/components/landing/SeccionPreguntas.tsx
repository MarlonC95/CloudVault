import { Plus } from 'lucide-react'
import { PREGUNTAS_FRECUENTES } from '../../data/landing'

/** Usa <details>, que ya se abre y cierra solo y funciona con teclado. */
function SeccionPreguntas() {
  return (
    <section id="preguntas" className="lp-seccion lp-seccion-gris">
      <div className="lp-contenedor" style={{ maxWidth: 780 }}>
        <div className="text-center mb-5">
          <span className="lp-etiqueta">Preguntas frecuentes</span>
          <h2 className="lp-titulo-seccion">¿Tienes dudas?</h2>
        </div>
        {PREGUNTAS_FRECUENTES.map((item) => (
          <details key={item.pregunta} className="lp-pregunta">
            <summary>
              {item.pregunta}
              <Plus size={20} />
            </summary>
            <p>{item.respuesta}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

export default SeccionPreguntas