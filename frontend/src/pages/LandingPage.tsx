import BarraNavegacion from '../components/landing/BarraNavegacion'
import SeccionHero from '../components/landing/SeccionHero'
import FranjaDatos from '../components/landing/FranjaDatos'
import SeccionCaracteristicas from '../components/landing/SeccionCaracteristicas'
import SeccionPasos from '../components/landing/SeccionPasos'
import SeccionPlanes from '../components/landing/SeccionPlanes'
import SeccionPreguntas from '../components/landing/SeccionPreguntas'
import PiePagina from '../components/landing/PiePagina'
import '../styles/landing.css'

/** Página pública de presentación. Quien ya tiene sesión va directo al dashboard (ver RutaPublica). */
function LandingPage() {
  return (
    <div className="lp">
      <BarraNavegacion />
      <main>
        <SeccionHero />
        <FranjaDatos />
        <SeccionCaracteristicas />
        <SeccionPasos />
        <SeccionPlanes />
        <SeccionPreguntas />
      </main>
      <PiePagina />
    </div>
  )
}

export default LandingPage