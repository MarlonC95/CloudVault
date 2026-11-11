import { History, Link2, Lock, Trash2, UploadCloud, Users, type LucideIcon } from 'lucide-react'

export interface Caracteristica {
  icono: LucideIcon
  titulo: string
  descripcion: string
}

export interface Paso {
  titulo: string
  descripcion: string
}

export interface PlanLanding {
  nombre: string
  precioMensual: number
  /** Total del año con 20% de descuento, igual que el backend. */
  precioAnual: number
  almacenamiento: string
  caracteristicas: string[]
  esPopular: boolean
}

export interface PreguntaFrecuente {
  pregunta: string
  respuesta: string
}

export const CARACTERISTICAS: Caracteristica[] = [
  {
    icono: UploadCloud,
    titulo: 'Subida directa a la nube',
    descripcion: 'Tus archivos viajan directo al almacenamiento con URLs prefirmadas, sin saturar el servidor.',
  },
  {
    icono: Users,
    titulo: 'Organizaciones y roles',
    descripcion: 'Trabaja en equipo con cuatro niveles de acceso: Propietario, Avanzado, Operativo y Lector.',
  },
  {
    icono: Trash2,
    titulo: 'Papelera de 30 días',
    descripcion: '¿Borraste algo por error? Lo recuperas desde la papelera durante 30 días.',
  },
  {
    icono: Link2,
    titulo: 'Comparte con enlaces',
    descripcion: 'Genera un enlace para que otras personas vean tus archivos, con o sin cuenta.',
  },
  {
    icono: History,
    titulo: 'Auditoría de acciones',
    descripcion: 'Cada acción importante queda registrada para saber quién hizo qué y cuándo.',
  },
  {
    icono: Lock,
    titulo: 'Sesiones seguras',
    descripcion: 'Inicio de sesión con tokens JWT que se renuevan solos y se invalidan al cerrar sesión.',
  },
]

export const PASOS: Paso[] = [
  { titulo: 'Crea tu cuenta', descripcion: 'Regístrate gratis y recibe tu espacio personal con 15 GB.' },
  { titulo: 'Sube y organiza', descripcion: 'Arrastra tus archivos, crea carpetas y encuentra todo rápido.' },
  { titulo: 'Comparte y colabora', descripcion: 'Invita a tu equipo con el rol adecuado o comparte un enlace.' },
]

// Mismos precios y beneficios que el catálogo del backend (subscriptions/services.py y database/seeds.sql).
export const PLANES_LANDING: PlanLanding[] = [
  {
    nombre: 'Gratuito',
    precioMensual: 0,
    precioAnual: 0,
    almacenamiento: '15 GB',
    caracteristicas: ['15 GB de almacenamiento', '1 usuario', 'Cifrado estándar', 'Soporte por comunidad'],
    esPopular: false,
  },
  {
    nombre: 'Pro PaaS',
    precioMensual: 29,
    precioAnual: 278,
    almacenamiento: '100 GB',
    caracteristicas: ['100 GB de almacenamiento', 'Hasta 5 usuarios', 'Cifrado de extremo a extremo', 'Versionado de archivos', 'Soporte 24/7'],
    esPopular: true,
  },
  {
    nombre: 'Empresarial',
    precioMensual: 99,
    precioAnual: 950,
    almacenamiento: '1 TB',
    caracteristicas: ['1 TB de almacenamiento', 'Usuarios ilimitados', 'Logs de auditoría avanzada', 'API dedicada', 'SLA del 99.9%'],
    esPopular: false,
  },
]

export const PREGUNTAS_FRECUENTES: PreguntaFrecuente[] = [
  {
    pregunta: '¿Necesito tarjeta para empezar?',
    respuesta: 'No. Al crear tu cuenta recibes el plan Gratuito con 15 GB, sin ningún pago.',
  },
  {
    pregunta: '¿Mis archivos pasan por el servidor de CloudVault?',
    respuesta: 'No. El servidor solo autoriza la subida; el archivo viaja directo al almacenamiento con una URL prefirmada.',
  },
  {
    pregunta: '¿Qué pasa si elimino un archivo?',
    respuesta: 'Va a la papelera y puedes restaurarlo durante 30 días. Después se elimina de forma definitiva.',
  },
  {
    pregunta: '¿Los pagos son reales?',
    respuesta: 'No. CloudVault es un proyecto académico: los pagos son simulados y nunca se cobra nada.',
  },
]