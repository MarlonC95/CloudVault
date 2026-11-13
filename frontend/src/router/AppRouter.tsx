import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import ArchivosProvider from '../context/ArchivosProvider'
import OrganizacionesProvider from '../context/OrganizacionesProvider'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import RegisterPage from '../pages/RegisterPage'
import RecoverPasswordPage from '../pages/RecoverPasswordPage'
import DashboardPage from '../pages/DashboardPage'
import PapeleraPage from '../pages/PapeleraPage'
import ProfilePage from '../pages/ProfilePage'
import PlanesPage from '../pages/PlanesPage'
import PagoPage from '../pages/PagoPage'
import AdministracionPage from '../pages/AdministracionPage'
import PlataformaPage from '../pages/PlataformaPage'
import MiembrosPage from '../pages/MiembrosPage'
import InvitacionesPage from '../pages/InvitacionesPage'
import CompartidosPage from '../pages/CompartidosPage'
import EnlacePublicoPage from '../pages/EnlacePublicoPage'
import { obtenerSesion } from '../services/authService'

function RutaProtegida() {
  // El provider vive aquí (no sobre todo el router) para cargar archivos solo con sesión
  // y reiniciar su estado al cerrar sesión.
  return obtenerSesion() ? (
    <OrganizacionesProvider><ArchivosProvider>
      <Outlet />
    </ArchivosProvider></OrganizacionesProvider>
  ) : (
    <Navigate to="/login" replace />
  )
}

function RutaPublica() {
  return obtenerSesion() ? <Navigate to="/dashboard" replace /> : <Outlet />
}

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* La Landing Page siempre es accesible, tengas o no sesión activa */}
        <Route path="/" element={<LandingPage />} />
        <Route element={<RutaPublica />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/registro" element={<RegisterPage />} />
          <Route path="/recuperar" element={<RecoverPasswordPage />} />
        </Route>
        <Route element={<RutaProtegida />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/papelera" element={<PapeleraPage />} />
          <Route path="/perfil" element={<ProfilePage />} />
          <Route path="/planes" element={<PlanesPage />} />
          <Route path="/planes/pago" element={<PagoPage />} />
          <Route path="/administracion" element={<AdministracionPage />} />
          <Route path="/administracion/plataforma" element={<PlataformaPage />} />
          <Route path="/organizacion/miembros" element={<MiembrosPage />} />
          <Route path="/invitaciones" element={<InvitacionesPage />} />
          <Route path="/compartidos" element={<CompartidosPage />} />
        </Route>
        {/* Fuera de ambas guardas: el enlace se abre con o sin sesión. */}
        <Route path="/s/:token" element={<EnlacePublicoPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter
