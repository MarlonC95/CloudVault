import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import ArchivosProvider from '../context/ArchivosProvider'
import LoginPage from '../pages/LoginPage'
import RegisterPage from '../pages/RegisterPage'
import RecoverPasswordPage from '../pages/RecoverPasswordPage'
import DashboardPage from '../pages/DashboardPage'
import PapeleraPage from '../pages/PapeleraPage'
import ProfilePage from '../pages/ProfilePage'
import PlanesPage from '../pages/PlanesPage'
import { obtenerSesion } from '../services/authService'

function RutaProtegida() {
  // El provider vive aquí (no sobre todo el router) para cargar archivos solo con sesión
  // y reiniciar su estado al cerrar sesión.
  return obtenerSesion() ? (
    <ArchivosProvider>
      <Outlet />
    </ArchivosProvider>
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
        </Route>
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter