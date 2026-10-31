import { Activity, Building2, DollarSign, HardDrive, Receipt, Users } from 'lucide-react'
import type { DesgloseAlmacenamiento, ResumenPlataforma } from '../../types/plataforma'
import { formatearFechaCorta } from '../../utils/fechas'
import {
  CODIGOS_PLAN,
  calcularPorcentaje,
  contarPlanes,
  formatearUsd,
  obtenerColorPlan,
  obtenerEtiquetaPlan,
  obtenerEtiquetaTipoMime,
} from '../../utils/plataforma'
import { COLOR_MARCA } from '../../theme/colores'
import TarjetaMetrica from '../administracion/TarjetaMetrica'
import ContenedorPanel from './ContenedorPanel'
import FilaProporcion from './FilaProporcion'

const COLOR_VERDE = '#16A34A'
const COLOR_VIOLETA = '#7C3AED'
const COLOR_AMBAR = '#D97706'
const COLORES_TIPO_ARCHIVO = [COLOR_MARCA, COLOR_VIOLETA, COLOR_VERDE, '#64748B']

interface PanelResumenPlataformaProps {
  resumen: ResumenPlataforma
  desglose: DesgloseAlmacenamiento
}

function PanelResumenPlataforma({ resumen, desglose }: PanelResumenPlataformaProps) {
  const totalSuscripciones = contarPlanes(resumen.distribucionPlanes)

  return (
    <>
      <p className="mb-3" style={{ fontSize: 12, color: '#64748B' }}>
        Periodo: {formatearFechaCorta(resumen.desde)} – {formatearFechaCorta(resumen.hasta)} (UTC). Usuarios, organizaciones y
        almacenamiento son una foto de hoy; la actividad y los ingresos corresponden al periodo.
      </p>

      <div className="row g-3 mb-4">
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Usuarios registrados"
            valor={String(resumen.totalUsuariosRegistrados)}
            detalle="cuentas en toda la plataforma"
            icono={<Users size={18} color={COLOR_MARCA} strokeWidth={1.6} />}
            color={COLOR_MARCA}
          />
        </div>
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Usuarios activos del periodo"
            valor={String(resumen.usuariosActivosPeriodo)}
            detalle="con inicio de sesión exitoso en el periodo"
            icono={<Activity size={18} color={COLOR_VERDE} strokeWidth={1.6} />}
            color={COLOR_VERDE}
            porcentaje={calcularPorcentaje(resumen.usuariosActivosPeriodo, resumen.totalUsuariosRegistrados)}
          />
        </div>
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Organizaciones"
            valor={String(resumen.totalOrganizaciones)}
            detalle="espacios personales y compartidos"
            icono={<Building2 size={18} color={COLOR_VIOLETA} strokeWidth={1.6} />}
            color={COLOR_VIOLETA}
          />
        </div>
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Almacenamiento agregado"
            valor={resumen.almacenamientoAgregadoLegible}
            detalle="suma de todos los espacios de trabajo"
            icono={<HardDrive size={18} color={COLOR_MARCA} strokeWidth={1.6} />}
            color={COLOR_MARCA}
          />
        </div>
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Ingresos mensuales estimados"
            valor={formatearUsd(resumen.ingresosMensualesEstimadosUsd)}
            detalle="suscripciones activas, equivalente mensual"
            icono={<DollarSign size={18} color={COLOR_AMBAR} strokeWidth={1.6} />}
            color={COLOR_AMBAR}
          />
        </div>
        <div className="col-12 col-sm-6 col-xl-4">
          <TarjetaMetrica
            etiqueta="Ingresos simulados del periodo"
            valor={formatearUsd(resumen.ingresosSimuladosPeriodoUsd)}
            detalle="pagos aprobados en el periodo"
            icono={<Receipt size={18} color={COLOR_AMBAR} strokeWidth={1.6} />}
            color={COLOR_AMBAR}
          />
        </div>
      </div>

      <div className="row g-4 align-items-start">
        <div className="col-12 col-lg-6">
          <ContenedorPanel titulo="Distribución de planes" subtitulo="Suscripciones vigentes por plan">
            <div style={{ padding: '20px 20px 4px' }}>
              {CODIGOS_PLAN.map((plan) => (
                <FilaProporcion
                  key={plan}
                  etiqueta={obtenerEtiquetaPlan(plan)}
                  valor={`${resumen.distribucionPlanes[plan]} suscripciones`}
                  porcentaje={calcularPorcentaje(resumen.distribucionPlanes[plan], totalSuscripciones)}
                  color={obtenerColorPlan(plan)}
                />
              ))}
            </div>
          </ContenedorPanel>
        </div>

        <div className="col-12 col-lg-6">
          <ContenedorPanel titulo="Almacenamiento por tipo de archivo" subtitulo="Archivos activos y en papelera">
            <div style={{ padding: '20px 20px 4px' }}>
              {desglose.porTipo.map((categoria, indice) => (
                <FilaProporcion
                  key={categoria.tipo}
                  etiqueta={obtenerEtiquetaTipoMime(categoria.tipo)}
                  valor={`${categoria.tamanoLegible} · ${categoria.porcentaje}%`}
                  porcentaje={categoria.porcentaje}
                  color={COLORES_TIPO_ARCHIVO[indice % COLORES_TIPO_ARCHIVO.length]}
                />
              ))}
            </div>
            <p className="mb-0" style={{ padding: '0 20px 16px', fontSize: 12, color: '#94A3B8' }}>
              Archivos en papelera: {desglose.papeleraLegible}
            </p>
          </ContenedorPanel>
        </div>
      </div>
    </>
  )
}

export default PanelResumenPlataforma