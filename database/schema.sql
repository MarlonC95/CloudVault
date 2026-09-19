-- Extensión para generación de identificadores únicos UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. PLANES
-- =====================================================
CREATE TABLE planes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    limite_almacenamiento_bytes BIGINT NOT NULL,
    precio NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- =====================================================
-- 2. ORGANIZACIONES
-- =====================================================
CREATE TABLE organizaciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(150) NOT NULL,
    almacenamiento_usado_bytes BIGINT NOT NULL DEFAULT 0,
    fecha_creacion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 3. USUARIOS
-- =====================================================
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correo_electronico VARCHAR(255) NOT NULL UNIQUE,
    contrasena_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    palabra_secreta_hash VARCHAR(255) NOT NULL,
    esta_activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 4. SUSCRIPCIONES
-- =====================================================
CREATE TABLE suscripciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    plan_id INT NOT NULL REFERENCES planes(id) ON DELETE RESTRICT,
    estado VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    periodo_inicio TIMESTAMP WITH TIME ZONE NOT NULL,
    periodo_fin TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_renovar BOOLEAN NOT NULL DEFAULT TRUE
);

-- =====================================================
-- 5. HISTORIAL_PAGOS
-- =====================================================
CREATE TABLE historial_pagos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    suscripcion_id UUID NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
    monto NUMERIC(10, 2) NOT NULL,
    estado VARCHAR(50) NOT NULL,
    referencia_transaccion VARCHAR(255) NOT NULL,
    fecha_pago TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 6. MIEMBROS_ORGANIZACION (RBAC)
-- =====================================================
CREATE TABLE miembros_organizacion (
    id BIGSERIAL PRIMARY KEY,
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nivel_rol SMALLINT NOT NULL CHECK (nivel_rol IN (0, 1, 2, 3)), -- 0: Owner, 1: Lector, 2: Operativo, 3: Avanzado
    fecha_union TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_miembro_org UNIQUE (organizacion_id, usuario_id)
);

-- =====================================================
-- 7. CARPETAS (Estructura Jerárquica Autorreferencial)
-- =====================================================
CREATE TABLE carpetas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    carpeta_padre_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    en_papelera BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_papelera TIMESTAMP WITH TIME ZONE,
    fecha_creacion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 8. ARCHIVOS
-- =====================================================
CREATE TABLE archivos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organizacion_id UUID NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE SET NULL,
    propietario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    nombre VARCHAR(255) NOT NULL,
    clave_s3 VARCHAR(500) NOT NULL UNIQUE,
    tamano_bytes BIGINT NOT NULL,
    tipo_mime VARCHAR(100) NOT NULL,
    en_papelera BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_papelera TIMESTAMP WITH TIME ZONE,
    fecha_subida TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 9. PERMISOS_RECURSO (ACL Interno Granular)
-- =====================================================
CREATE TABLE permisos_recurso (
    id BIGSERIAL PRIMARY KEY,
    archivo_id UUID REFERENCES archivos(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo_permiso VARCHAR(50) NOT NULL, -- 'read', 'write', 'admin'
    CONSTRAINT chk_recurso_exclusivo CHECK (
        (archivo_id IS NOT NULL AND carpeta_id IS NULL) OR
        (archivo_id IS NULL AND carpeta_id IS NOT NULL)
    )
);

-- =====================================================
-- 10. ENLACES_PUBLICOS
-- =====================================================
CREATE TABLE enlaces_publicos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_random VARCHAR(255) NOT NULL UNIQUE,
    archivo_id UUID REFERENCES archivos(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetas(id) ON DELETE CASCADE,
    contrasena_hash VARCHAR(255),
    fecha_expiracion TIMESTAMP WITH TIME ZONE,
    fecha_creacion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_enlace_recurso_exclusivo CHECK (
        (archivo_id IS NOT NULL AND carpeta_id IS NULL) OR
        (archivo_id IS NULL AND carpeta_id IS NOT NULL)
    )
);

-- =====================================================
-- ÍNDICES ESTRATÉGICOS (Rendimiento RNF-02 y RNF-04)
-- =====================================================
CREATE INDEX idx_archivos_org ON archivos(organizacion_id);
CREATE INDEX idx_archivos_carpeta ON archivos(carpeta_id);
CREATE INDEX idx_archivos_papelera ON archivos(en_papelera, fecha_papelera);
CREATE INDEX idx_carpetas_org ON carpetas(organizacion_id);
CREATE INDEX idx_carpetas_padre ON carpetas(carpeta_padre_id);
CREATE INDEX idx_carpetas_papelera ON carpetas(en_papelera, fecha_papelera);
CREATE INDEX idx_miembros_org ON miembros_organizacion(organizacion_id, usuario_id);
-- =====================================================
-- 1. SOPORTE PARA 2FA / TOTP (RF-04)
-- =====================================================
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- =====================================================
-- 2. FRECUENCIA DE FACTURACIÓN (RF-11: MENSUAL / ANUAL)
-- =====================================================
ALTER TABLE suscripciones 
ADD COLUMN IF NOT EXISTS intervalo VARCHAR(20) NOT NULL DEFAULT 'MONTHLY' 
CHECK (intervalo IN ('MONTHLY', 'YEARLY'));

-- =====================================================
-- 3. PERMITIR RECURSOS PERSONALES DIRECTOS (Opcional a nivel BD)
-- =====================================================
-- Permite que archivos y carpetas pertenezcan a un usuario particular
-- sin obligarlo a crear una organización si el backend no lo requiere.
ALTER TABLE carpetas ALTER COLUMN organizacion_id DROP NOT NULL;
ALTER TABLE archivos ALTER COLUMN organizacion_id DROP NOT NULL;

-- =====================================================
-- 4. TABLA DE REGISTROS DE AUDITORÍA (RF-14: Audit Logs)
-- =====================================================
CREATE TABLE IF NOT EXISTS logs_auditoria (
    id BIGSERIAL PRIMARY KEY,
    organizacion_id UUID REFERENCES organizaciones(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    accion VARCHAR(100) NOT NULL,            -- 'FILE_UPLOAD', 'FILE_DELETE', 'ROLE_CHANGE', etc.
    ip_origen VARCHAR(45),
    detalles JSONB,                          -- Metadatos adicionales del evento
    fecha_evento TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_auditoria_org ON logs_auditoria(organizacion_id, fecha_evento DESC);