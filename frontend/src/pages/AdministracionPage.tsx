import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Globe, HardDrive, Info, Shield, Users, X } from 'lucide-react'
import DashboardLayout from '../components/layout/DashboardLayout'
import TarjetaMetrica from '../components/administracion/TarjetaMetrica'
import TablaMiembros from '../components/administracion/TablaMiembros'
import PanelAuditoria from '../components/administracion/PanelAuditoria'
import ModalInvitarMiembro from '../components/administracion/ModalInvitarMiembro'
import ModalCambiarRol from '../components/administracion/ModalCambiarRol'
import ModalConfirmacion from '../components/administracion/ModalConfirmacion'
import { obtenerSesion } from '../services/authService'
import { EVENTOS_EJEMPLO, MIEMBROS_EJEMPLO, RESUMEN_ORGANIZACION_EJEMPLO } from '../data/administracionEjemplo'
import { convertirEventosACsv, contarEventosCriticos, contarMiembrosActivos, obtenerEtiquetaRol } from '../utils/administracion'
import { descargarTexto } from '../utils/descargas'
import { COLOR_MARCA } from '../theme/colores'
import type { EventoAuditoria, MiembroOrganizacion, RolMiembro, SeveridadEvento, TipoEvento } from '../types/administracion'

const COLOR_VERDE = '#16A34A'
const COLOR_GRIS = '#64748B'

function AdministracionPage() {
  // TODO(backend): sustituir estos estados por datos reales cuando existan los endpoints de administración.
  const [miembros, setMiembros] = useState<MiembroOrganizacion[]>(MIEMBROS_EJEMPLO)
  const [eventos, setEventos] = useState<EventoAuditoria[]>(EVENTOS_EJEMPLO)

  const [mostrandoInvitacion, setMostrandoInvitacion] = useState(false)
  const [miembroEnEdicion, setMiembroEnEdicion] = useState<MiembroOrganizacion | null>(null)
  const [miembroPorQuitar, setMiembroPorQuitar] = useState<MiembroOrganizacion | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const resumen = RESUMEN_ORGANIZACION_EJEMPLO
  const miembrosActivos = contarMiembrosActivos(miembros)
  const alertasCriticas = contarEventosCriticos(eventos)

  function registrarEvento(tipo: TipoEvento, descripcion: string, severidad: SeveridadEvento) {
    const nuevoEvento: EventoAuditoria = {
      id: `evento-${Date.now()}`,
      tipo,
      descripcion,
      fecha: new Date().toISOString(),
      severidad,
    }
    setEventos((eventosActuales) => [nuevoEvento, ...eventosActuales])
  }

  function nombreDelUsuarioActual(): string {
    return obtenerSesion()?.usuario.nombreCompleto ?? 'Un administrador'
  }

  function invitarMiembro(correo: string, rol: RolMiembro) {
    const nuevoMiembro: MiembroOrganizacion = {
      id: `miembro-${Date.now()}`,
      nombreCompleto: correo.split('@')[0],
      correoElectronico: correo,
      rol,
      estado: 'pendiente',
    }
    setMiembros((miembrosActuales) => [...miembrosActuales, nuevoMiembro])
    registrarEvento('seguridad', `${nombreDelUsuarioActual()} invitó a ${correo} como ${obtenerEtiquetaRol(rol)}`, 'info')
    setMostrandoInvitacion(false)
    setAviso(`Invitación enviada a ${correo}.`)
  }

  function cambiarRol(miembro: MiembroOrganizacion, nuevoRol: RolMiembro) {
    setMiembros((miembrosActuales) =>
      miembrosActuales.map((actual) => (actual.id === miembro.id ? { ...actual, rol: nuevoRol } : actual)),
    )
    registrarEvento(
      'seguridad',
      `${nombreDelUsuarioActual()} cambió el rol de ${miembro.nombreCompleto} a ${obtenerEtiquetaRol(nuevoRol)}`,
      'info',
    )
    setMiembroEnEdicion(null)
    setAviso(`Ahora ${miembro.nombreCompleto} tiene el rol ${obtenerEtiquetaRol(nuevoRol)}.`)
  }

  function quitarMiembro(miembro: MiembroOrganizacion) {
    setMiembros((miembrosActuales) => miembrosActuales.filter((actual) => actual.id !== miembro.id))
    registrarEvento('seguridad', `${nombreDelUsuarioActual()} quitó a ${miembro.nombreCompleto} de la organización`, 'advertencia')
    setMiembroPorQuitar(null)
    setAviso(`${miembro.nombreCompleto} ya no forma parte de la organización.`)
  }

  function reenviarInvitacion(miembro: MiembroOrganizacion) {
    setAviso(`Invitación reenviada a ${miembro.correoElectronico}.`)
  }

  function exportarAuditoria() {
    descargarTexto('auditoria-cloudvault.csv', convertirEventosACsv(eventos), 'text/csv;charset=utf-8')
  }

  return (
    <DashboardLayout seccionActiva="administracion">
      <div style={{ padding: 32 }}>
        <header className="d-flex align-items-start justify-content-between flex-wrap gap-3 mb-4">
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 700, color: '#0F172A', letterSpacing: '-0.018em', marginBottom: 6 }}>
              Panel de administración
            </h1>
            <p className="mb-0" style={{ fontSize: 14, color: '#64748B', lineHeight: 1.55 }}>
              Gestión de miembros de la organización, roles, almacenamiento y auditoría de seguridad.
            </p>
          </div>
          <Link
            to="/administracion/plataforma"
            className="d-inline-flex align-items-center gap-2 text-decoration-none"
            style={{ border: '1px solid #E2E8F0', background: '#fff', borderRadius: 10, padding: '8px 14px', fontSize: 12, fontWeight: 600, color: COLOR_MARCA }}
          >
            <Globe size={14} />
            Panel de plataforma
          </Link>
        </header>

        <div
          role="note"
          className="d-flex align-items-start gap-2 mb-4"
          style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 12, padding: '10px 14px', color: '#1E40AF', fontSize: 12 }}
        >
          <Info size={15} className="flex-shrink-0" style={{ marginTop: 1 }} />
          <span>
            Vista con datos de ejemplo: los endpoints de administración todavía no existen en el backend (contrato, sección 6).
            Las acciones funcionan solo dentro de esta pantalla.
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

        <div className="row g-3 mb-4">
          <div className="col-12 col-sm-6 col-xl-3">
            <TarjetaMetrica
              etiqueta="Almacenamiento consumido"
              valor={resumen.almacenamientoUsadoLegible}
              detalle={`de ${resumen.cuotaLegible} usados — ${resumen.porcentajeAlmacenamiento}%`}
              icono={<HardDrive size={18} color={COLOR_MARCA} strokeWidth={1.6} />}
              color={COLOR_MARCA}
              porcentaje={resumen.porcentajeAlmacenamiento}
            />
          </div>
          <div className="col-12 col-sm-6 col-xl-3">
            <TarjetaMetrica
              etiqueta="Usuarios activos"
              valor={`${miembrosActivos} / ${miembros.length}`}
              detalle="miembros en la organización"
              icono={<Users size={18} color={COLOR_VERDE} strokeWidth={1.6} />}
              color={COLOR_VERDE}
            />
          </div>
          <div className="col-12 col-sm-6 col-xl-3">
            <TarjetaMetrica
              etiqueta="Estado del servicio"
              valor={resumen.disponibilidadServicio}
              detalle="SLA de disponibilidad"
              icono={<Activity size={18} color={COLOR_VERDE} strokeWidth={1.6} />}
              color={COLOR_VERDE}
              conIndicador
            />
          </div>
          <div className="col-12 col-sm-6 col-xl-3">
            <TarjetaMetrica
              etiqueta="Alertas de seguridad"
              valor={String(alertasCriticas)}
              detalle="alertas críticas en el registro"
              icono={<Shield size={18} color={alertasCriticas > 0 ? '#DC2626' : COLOR_GRIS} strokeWidth={1.6} />}
              color={alertasCriticas > 0 ? '#DC2626' : COLOR_GRIS}
            />
          </div>
        </div>

        <div className="row g-4 align-items-start">
          <div className="col-12 col-xl-7">
            <TablaMiembros
              miembros={miembros}
              onInvitar={() => setMostrandoInvitacion(true)}
              onEditar={setMiembroEnEdicion}
              onReenviar={reenviarInvitacion}
              onQuitar={setMiembroPorQuitar}
            />
          </div>
          <div className="col-12 col-xl-5">
            <PanelAuditoria eventos={eventos} onExportar={exportarAuditoria} />
          </div>
        </div>
      </div>

      {mostrandoInvitacion && (
        <ModalInvitarMiembro miembros={miembros} onCerrar={() => setMostrandoInvitacion(false)} onInvitar={invitarMiembro} />
      )}
      {miembroEnEdicion && (
        <ModalCambiarRol
          miembro={miembroEnEdicion}
          onCerrar={() => setMiembroEnEdicion(null)}
          onGuardar={(nuevoRol) => cambiarRol(miembroEnEdicion, nuevoRol)}
        />
      )}
      {miembroPorQuitar && (
        <ModalConfirmacion
          titulo={miembroPorQuitar.estado === 'pendiente' ? 'Cancelar invitación' : 'Quitar de la organización'}
          mensaje={
            miembroPorQuitar.estado === 'pendiente'
              ? `Se cancelará la invitación enviada a ${miembroPorQuitar.correoElectronico}.`
              : `${miembroPorQuitar.nombreCompleto} perderá el acceso a los archivos de la organización.`
          }
          etiquetaConfirmar={miembroPorQuitar.estado === 'pendiente' ? 'Cancelar invitación' : 'Quitar'}
          onConfirmar={() => quitarMiembro(miembroPorQuitar)}
          onCerrar={() => setMiembroPorQuitar(null)}
        />
      )}
    </DashboardLayout>
  )
}

export default AdministracionPage