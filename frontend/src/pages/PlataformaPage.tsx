import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Info, X } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import PestanasPlataforma from '../components/plataforma/PestanasPlataforma'
import PanelResumenPlataforma from '../components/plataforma/PanelResumenPlataforma'
import PanelUsuariosPlataforma from '../components/plataforma/PanelUsuariosPlataforma'
import PanelOrganizacionesPlataforma from '../components/plataforma/PanelOrganizacionesPlataforma'
import PanelAuditoriaPlataforma from '../components/plataforma/PanelAuditoriaPlataforma'
import ModalEstadoCuenta from '../components/plataforma/ModalEstadoCuenta'
import { obtenerSesion } from '../services/authService'
import {
  DESGLOSE_ALMACENAMIENTO_EJEMPLO,
  EVENTOS_PLATAFORMA_EJEMPLO,
  ORGANIZACIONES_PLATAFORMA_EJEMPLO,
  RESUMEN_PLATAFORMA_EJEMPLO,
  USUARIOS_PLATAFORMA_EJEMPLO,
} from '../data/plataformaEjemplo'
import { descargarTexto } from '../utils/descargas'
import { convertirEventosPlataformaACsv, obtenerIdPanel, obtenerIdPestana } from '../utils/plataforma'
import { COLOR_MARCA } from '../theme/colores'
import type { EventoPlataforma, PestanaPlataforma, UsuarioPlataforma } from '../types/plataforma'

function PlataformaPage() {
  // TODO(backend): sustituir estos estados por datos reales cuando existan los endpoints de administración.
  const [usuarios, setUsuarios] = useState<UsuarioPlataforma[]>(USUARIOS_PLATAFORMA_EJEMPLO)
  const [eventos, setEventos] = useState<EventoPlataforma[]>(EVENTOS_PLATAFORMA_EJEMPLO)

  const [pestanaActiva, setPestanaActiva] = useState<PestanaPlataforma>('resumen')
  const [usuarioEnRevision, setUsuarioEnRevision] = useState<UsuarioPlataforma | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const usuarioActual = obtenerSesion()?.usuario

  function cambiarEstadoCuenta(usuario: UsuarioPlataforma, motivo: string) {
    const quedaActivo = !usuario.estaActivo
    setUsuarios((actuales) => actuales.map((actual) => (actual.id === usuario.id ? { ...actual, estaActivo: quedaActivo } : actual)))

    const nuevoEvento: EventoPlataforma = {
      id: `evt-${Date.now()}`,
      accion: quedaActivo ? 'ADMIN_USER_ENABLED' : 'ADMIN_USER_DISABLED',
      usuarioNombre: usuarioActual?.nombreCompleto ?? 'Un superusuario',
      organizacionNombre: null,
      fechaEvento: new Date().toISOString(),
      detalles: { usuario_id: usuario.id, motivo },
    }
    setEventos((actuales) => [nuevoEvento, ...actuales])

    setUsuarioEnRevision(null)
    setAviso(quedaActivo ? `La cuenta de ${usuario.nombreCompleto} quedó habilitada.` : `La cuenta de ${usuario.nombreCompleto} quedó deshabilitada.`)
  }

  function exportarAuditoria(eventosAExportar: EventoPlataforma[]) {
    descargarTexto('auditoria-plataforma.csv', convertirEventosPlataformaACsv(eventosAExportar), 'text/csv;charset=utf-8')
  }

  return (
    <DashboardLayout seccionActiva="administracion">
      <div style={{ padding: 32 }}>
        <Link
          to="/administracion"
          className="d-inline-flex align-items-center gap-1 mb-3 text-decoration-none"
          style={{ fontSize: 13, fontWeight: 600, color: COLOR_MARCA }}
        >
          <ArrowLeft size={14} />
          Volver a la administración de la organización
        </Link>

        <header className="mb-4">
          <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.018em', marginBottom: 6 }}>
            Panel de plataforma
          </h1>
          <p className="mb-0" style={{ fontSize: 14, color: '#64748B', lineHeight: 1.55 }}>
            Métricas globales, cuentas de usuario, organizaciones y auditoría de toda la plataforma. Solo para superusuarios.
          </p>
        </header>

        <div
          role="note"
          className="d-flex align-items-start gap-2 mb-4"
          style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 12, padding: '10px 14px', color: '#1E40AF', fontSize: 12 }}
        >
          <Info size={15} className="flex-shrink-0" style={{ marginTop: 1 }} />
          <span>
            Vista con datos de ejemplo: los endpoints de administración todavía no existen en el backend (contrato, sección 6).
            Cuando existan, el servidor será quien valide si la cuenta es superusuaria.
          </span>
        </div>

        {aviso && (
          <div
            role="status"
            className="d-flex align-items-center justify-content-between gap-2 mb-4"
            style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 12, padding: '10px 14px', color: '#166534', fontSize: 13 }}
          >
            <span>{aviso}</span>
            <button type="button" className="btn btn-sm p-0" onClick={() => setAviso(null)} aria-label="Cerrar aviso">
              <X size={16} />
            </button>
          </div>
        )}

        <PestanasPlataforma activa={pestanaActiva} onCambiar={setPestanaActiva} />

        <div role="tabpanel" id={obtenerIdPanel(pestanaActiva)} aria-labelledby={obtenerIdPestana(pestanaActiva)}>
          {pestanaActiva === 'resumen' && (
            <PanelResumenPlataforma resumen={RESUMEN_PLATAFORMA_EJEMPLO} desglose={DESGLOSE_ALMACENAMIENTO_EJEMPLO} />
          )}
          {pestanaActiva === 'usuarios' && (
            <PanelUsuariosPlataforma
              usuarios={usuarios}
              correoUsuarioActual={usuarioActual?.correoElectronico}
              onCambiarEstado={setUsuarioEnRevision}
            />
          )}
          {pestanaActiva === 'organizaciones' && <PanelOrganizacionesPlataforma organizaciones={ORGANIZACIONES_PLATAFORMA_EJEMPLO} />}
          {pestanaActiva === 'auditoria' && <PanelAuditoriaPlataforma eventos={eventos} onExportar={exportarAuditoria} />}
        </div>
      </div>

      {usuarioEnRevision && (
        <ModalEstadoCuenta
          usuario={usuarioEnRevision}
          onCerrar={() => setUsuarioEnRevision(null)}
          onConfirmar={(motivo) => cambiarEstadoCuenta(usuarioEnRevision, motivo)}
        />
      )}
    </DashboardLayout>
  )
}

export default PlataformaPage