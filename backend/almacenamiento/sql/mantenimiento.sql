
-- Complemento aprobado por el responsable SQL: tabla 14 en public.
-- Su aplicación compartida pertenece a ese responsable, nunca al runtime.
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
    FOR EACH ROW EXECUTE FUNCTION public.trigger_actualizar_marca_tiempo();

GRANT SELECT ON public.trabajos_mantenimiento TO lector_cloudvault;
-- El responsable SQL asigna SELECT/INSERT/UPDATE al rol real de Django.
-- No se inventa aquí un nombre de rol de desarrollo.
