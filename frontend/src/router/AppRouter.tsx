import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'
import RegisterPage from '../pages/RegisterPage'
import RecoverPasswordPage from '../pages/RecoverPasswordPage'
import DashboardPage from '../pages/DashboardPage'
import { obtenerSesion } from '../services/authService'

function RutaDashboard() {
  return obtenerSesion() ? <DashboardPage /> : <Navigate to="/login" replace />
}

function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/registro" element={<RegisterPage />} />
        <Route path="/recuperar" element={<RecoverPasswordPage />} />
        <Route path="/dashboard" element={<RutaDashboard />} />
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRouter
