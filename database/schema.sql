-- Habilitar extensión para UUIDs criptográficos
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- 1. TABLA: organizaciones
-- =====================================================
CREATE TABLE IF NOT EXISTS organizaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(150) NOT NULL,
    slug VARCHAR(150) NOT NULL UNIQUE,
    almacenamiento_usado_bytes BIGINT NOT NULL DEFAULT 0,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_organizaciones_slug ON organizaciones(slug);

-- =====================================================
-- 2. TABLA: planes
-- =====================================================
CREATE TABLE IF NOT EXISTS planes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    limite_almacenamiento_bytes BIGINT NOT NULL,
    precio NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 3. TABLA: usuarios
-- =====================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_completo VARCHAR(150) NOT NULL,
    correo_electronico VARCHAR(255) NOT NULL UNIQUE,
    contrasena_hash VARCHAR(255) NOT NULL,
    palabra_secreta_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(64) DEFAULT NULL,
    is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios(correo_electronico);

-- =====================================================
-- 4. TABLA: suscripciones
-- =====================================================
CREATE TABLE IF NOT EXISTS suscripciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    plan_id INT NOT NULL REFERENCES planes(id) ON DELETE RESTRICT,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' 
        CHECK (estado IN ('ACTIVE', 'PAST_DUE', 'CANCELED')),
    intervalo VARCHAR(20) NOT NULL DEFAULT 'MONTHLY' 
        CHECK (intervalo IN ('MONTHLY', 'YEARLY')),
    periodo_inicio TIMESTAMP WITH TIME ZONE NOT NULL,
    periodo_fin TIMESTAMP WITH TIME ZONE NOT NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suscripciones_org ON suscripciones(organizacion_id);

-- =====================================================
-- 5. TABLA: historial_pagos
-- =====================================================
CREATE TABLE IF NOT EXISTS historial_pagos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suscripcion_id UUID NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
    pasarela_transaccion_id VARCHAR(100),
    monto NUMERIC(10, 2) NOT NULL,
    moneda VARCHAR(3) NOT NULL DEFAULT 'USD',
    estado VARCHAR(20) NOT NULL DEFAULT 'COMPLETED' 
        CHECK (estado IN ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED')),
    url_recibo TEXT,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pagos_suscripcion ON historial_pagos(suscripcion_id);

-- =====================================================
-- 6. TABLA: miembros_organizacion
-- =====================================================
CREATE TABLE IF NOT EXISTS miembros_organizacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nivel_rol SMALLINT NOT NULL DEFAULT 1 
        CHECK (nivel_rol IN (0, 1, 2, 3)), -- 0: Admin/Propietario, 1: Lector, 2: Operativo, 3: Avanzado
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_miembro_org_usuario UNIQUE (organizacion_id, usuario_id)
);

CREATE INDEX IF NOT EXISTS idx_miembros_org_user ON miembros_organizacion(organizacion_id, usuario_id);

-- =====================================================
-- 7. TABLA: carpetas
-- =====================================================
CREATE TABLE IF NOT EXISTS carpetas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE,
    carpeta_padre_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    propietario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    nombre VARCHAR(255) NOT NULL,
    ruta_completa TEXT NOT NULL DEFAULT '/',
    en_papelera BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_papelera TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_carpetas_org_padre ON carpetas(organizacion_id, carpeta_padre_id);
CREATE INDEX IF NOT EXISTS idx_carpetas_papelera ON carpetas(en_papelera, fecha_papelera);

-- =====================================================
-- 8. TABLA: archivos
-- =====================================================
CREATE TABLE IF NOT EXISTS archivos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE SET NULL,
    propietario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    nombre_original VARCHAR(255) NOT NULL,
    clave_s3 VARCHAR(255) NOT NULL UNIQUE,
    tamano_bytes BIGINT NOT NULL DEFAULT 0,
    tipo_mime VARCHAR(100) NOT NULL,
    checksum_sha256 VARCHAR(64),
    en_papelera BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_papelera TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_archivos_carpeta ON archivos(carpeta_id);
CREATE INDEX IF NOT EXISTS idx_archivos_papelera ON archivos(en_papelera, fecha_papelera);
CREATE INDEX IF NOT EXISTS idx_archivos_org ON archivos(organizacion_id);

-- =====================================================
-- 9. TABLA: permisos_recurso (ACL)
-- =====================================================
CREATE TABLE IF NOT EXISTS permisos_recurso (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    archivo_id UUID REFERENCES archivos(id) ON DELETE CASCADE,
    tipo_permiso VARCHAR(20) NOT NULL 
        CHECK (tipo_permiso IN ('LECTURA', 'ESCRITURA', 'ADMINISTRACION')),
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_permiso_destino EXCLUDE USING gist (
        id WITH =
    ) WHERE (
        (carpeta_id IS NULL AND archivo_id IS NULL) OR 
        (carpeta_id IS NOT NULL AND archivo_id IS NOT NULL)
    ) DEFERRABLE INITIALLY IMMEDIATE
);

-- Si la extensión btree_gist no está habilitada, se asegura la restricción estándar:
ALTER TABLE permisos_recurso DROP CONSTRAINT IF EXISTS chk_permiso_mutuo_excluyente;
ALTER TABLE permisos_recurso ADD CONSTRAINT chk_permiso_mutuo_excluyente 
    CHECK (
        (carpeta_id IS NOT NULL AND archivo_id IS NULL) OR 
        (carpeta_id IS NULL AND archivo_id IS NOT NULL)
    );

CREATE INDEX IF NOT EXISTS idx_permisos_usuario ON permisos_recurso(usuario_id);

-- =====================================================
-- 10. TABLA: enlaces_publicos
-- =====================================================
CREATE TABLE IF NOT EXISTS enlaces_publicos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_random VARCHAR(64) NOT NULL UNIQUE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    archivo_id UUID REFERENCES archivos(id) ON DELETE CASCADE,
    creado_por_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    contrasena_hash VARCHAR(255) DEFAULT NULL,
    fecha_expiracion TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    total_descargas INT NOT NULL DEFAULT 0,
    limite_descargas INT DEFAULT NULL,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_enlace_mutuo_excluyente CHECK (
        (carpeta_id IS NOT NULL AND archivo_id IS NULL) OR 
        (carpeta_id IS NULL AND archivo_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_enlaces_token ON enlaces_publicos(token_random);

-- =====================================================
-- 11. TABLA: logs_auditoria
-- =====================================================
CREATE TABLE IF NOT EXISTS logs_auditoria (
    id BIGSERIAL PRIMARY KEY,
    organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    accion VARCHAR(100) NOT NULL,
    ip_origen VARCHAR(45),
    detalles JSONB,
    fecha_evento TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_auditoria_org ON logs_auditoria(organizacion_id, fecha_evento DESC);

-- Agregar columna slug con restricción única
ALTER TABLE organizaciones 
ADD COLUMN IF NOT EXISTS slug VARCHAR(150) UNIQUE;

-- Agregar columnas de auditoría temporal
ALTER TABLE organizaciones 
ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE archivos 
ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
-- =============================================================================
-- TABLA 12: sesiones_carga
-- Reserva preventiva de cuota en concurrencia y rastreo de cargas activas
-- =============================================================================
CREATE TABLE IF NOT EXISTS sesiones_carga (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archivo_id UUID NOT NULL UNIQUE,
    solicitante_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE SET NULL,
    nombre VARCHAR(255) NOT NULL,
    tipo_mime VARCHAR(100) NOT NULL,
    tamano_bytes BIGINT NOT NULL CHECK (tamano_bytes >= 0),
    checksum_sha256 VARCHAR(64) 
        CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'),
    etag VARCHAR(255),
    clave_temporal VARCHAR(1024) NOT NULL UNIQUE,
    expira_en TIMESTAMPTZ NOT NULL,
    estado VARCHAR(10) NOT NULL DEFAULT 'PENDING'
        CHECK (estado IN ('PENDING', 'CONFIRMED', 'CANCELED', 'EXPIRED')),
    resultado_confirmacion JSONB,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (expira_en > creado_en)
);

CREATE INDEX IF NOT EXISTS idx_sesiones_cuota_pendiente
    ON sesiones_carga (organizacion_id, expira_en) WHERE estado = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_sesiones_solicitante 
    ON sesiones_carga (solicitante_id);

DROP TRIGGER IF EXISTS trg_actualizar_sesiones_carga ON sesiones_carga;
CREATE TRIGGER trg_actualizar_sesiones_carga
    BEFORE UPDATE ON sesiones_carga
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

-- =============================================================================
-- TABLA 13: intentos_publicacion
-- Ledger técnico de confirmación e idempotencia con el Bucket S3 / Tigris
-- =============================================================================
CREATE TABLE IF NOT EXISTS intentos_publicacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sesion_id UUID NOT NULL UNIQUE REFERENCES sesiones_carga(id) ON DELETE RESTRICT,
    clave_final VARCHAR(1024) NOT NULL UNIQUE,
    etag_origen VARCHAR(255) NOT NULL,
    version_origen VARCHAR(255),
    checksum_origen VARCHAR(64),
    etag_final VARCHAR(255),
    version_final VARCHAR(255),
    estado VARCHAR(10) NOT NULL DEFAULT 'PREPARED'
        CHECK (estado IN ('PREPARED', 'PUBLISHED', 'ABANDONED', 'CLEANED')),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS trg_actualizar_intentos_publicacion ON intentos_publicacion;
CREATE TRIGGER trg_actualizar_intentos_publicacion
    BEFORE UPDATE ON intentos_publicacion
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

-- Conceder permisos de lectura al rol de evaluación lector_cloudvault
GRANT SELECT ON sesiones_carga TO lector_cloudvault;
GRANT SELECT ON intentos_publicacion TO lector_cloudvault;

CREATE TABLE IF NOT EXISTS public.trabajos_mantenimiento (
    sesion_id UUID PRIMARY KEY REFERENCES public.sesiones_carga(id) ON DELETE RESTRICT,
    cancelar BOOLEAN NOT NULL DEFAULT FALSE,
    copia_concluida BOOLEAN NOT NULL DEFAULT FALSE,
    estado VARCHAR(16) NOT NULL DEFAULT 'PENDING'
        CHECK (estado IN ('PENDING', 'RETRY', 'RECONCILE', 'VERIFIED')),
    intentos BIGINT NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    fallos_consecutivos INTEGER NOT NULL DEFAULT 0 CHECK (fallos_consecutivos >= 0),
    proximo_intento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    causa VARCHAR(32) NOT NULL DEFAULT '' CHECK (causa IN (
        '', 'URL_VIGENTE', 'COPY_AMBIGUO', 'REFERENCIADO', 'DEPENDENCIA',
        'S3', 'SQL', 'INTEGRIDAD', 'OCUPADO', 'RECUPERACION', 'ERROR')),
    verificado_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (estado <> 'VERIFIED' OR verificado_en IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_mantenimiento_proximo
    ON public.trabajos_mantenimiento (proximo_intento, sesion_id);

DROP TRIGGER IF EXISTS trg_actualizar_trabajos_mantenimiento ON public.trabajos_mantenimiento;
CREATE TRIGGER trg_actualizar_trabajos_mantenimiento
    BEFORE UPDATE ON public.trabajos_mantenimiento
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

GRANT SELECT ON public.trabajos_mantenimiento TO lector_cloudvault; --