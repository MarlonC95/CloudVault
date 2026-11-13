import { Mail } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import PanelInvitaciones from '../components/organizaciones/PanelInvitaciones'
import { useOrganizacion } from '../context/organizacionesContexto'
import { COLOR_ICONO_FONDO, COLOR_MARCA } from '../theme/colores'

export default function InvitacionesPage() {
  const { organizacion, ejecutar } = useOrganizacion()
  const puedeInvitar = organizacion.tipo === 'COMPARTIDO' && organizacion.nivelRol === 0

  return (
    <DashboardLayout seccionActiva="miembros">
      <div style={{ padding: '32px 24px', width: '100%', maxWidth: '940px', margin: '0 auto' }}>
        <header className="d-flex align-items-center gap-3 mb-4">
          <div
            className="d-flex align-items-center justify-content-center flex-shrink-0"
            style={{ width: '48px', height: '48px', borderRadius: '14px', backgroundColor: COLOR_ICONO_FONDO }}
          >
            <Mail size={24} color={COLOR_MARCA} />
          </div>
          <div>
            <h1 className="fw-bold mb-1" style={{ fontSize: '26px', color: '#0F172A', letterSpacing: '-0.02em' }}>
              Centro de Invitaciones
            </h1>
            <p className="mb-0" style={{ fontSize: '14px', color: '#64748B' }}>
              Consulta las invitaciones que has recibido o invita a colaboradores a tus espacios compartidos.
            </p>
          </div>
        </header>

        <div className="d-flex flex-column gap-4">
          {/* Si el espacio actual es compartido y eres propietario, muestra también el formulario de envío */}
          {puedeInvitar && (
            <PanelInvitaciones organizacionId={organizacion.id} ejecutar={ejecutar} />
          )}
          <PanelInvitaciones />
        </div>
      </div>
    </DashboardLayout>
  )
}
