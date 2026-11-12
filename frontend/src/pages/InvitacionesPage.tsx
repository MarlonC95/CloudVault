import { Link } from 'react-router-dom'
import PanelInvitaciones from '../components/organizaciones/PanelInvitaciones'

export default function InvitacionesPage() {
  return (
    <main className="container py-4" style={{ maxWidth: 760 }}>
      <Link to="/dashboard" className="btn btn-sm btn-outline-secondary mb-3">Volver a CloudVault</Link>
      <h1 className="h3 mb-3">Invitaciones</h1>
      <PanelInvitaciones />
    </main>
  )
}
