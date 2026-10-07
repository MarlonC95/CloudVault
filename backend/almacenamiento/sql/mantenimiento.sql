-- Complemento técnico de Dani. Instalación por el responsable de SQL.
-- No altera el esquema de referencia ni instala triggers/roles de negocio.
-- Solo se aplica automáticamente en el PostgreSQL desechable de los tests.
CREATE SCHEMA IF NOT EXISTS almacenamiento_tecnico;
CREATE TABLE IF NOT EXISTS almacenamiento_tecnico.trabajos_mantenimiento (
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
    ON almacenamiento_tecnico.trabajos_mantenimiento (proximo_intento, sesion_id);
