-- Compartir archivos y carpetas (enlaces y permisos por usuario), como en Google Drive.
-- Lo aplica el DBA sobre public en una transacción; si falla, no queda nada a medias.
-- Requisitos previos (si no se cumplen, el script falla y no cambia nada):
--   * enlaces_publicos vacía: creado_por_id es NOT NULL.
--   * permisos_recurso solo con tipo_permiso LECTURA/ESCRITURA y sin duplicados recurso+usuario.
-- No hay GRANT nuevos: preparar_public.sql ya da permisos sobre ambas tablas y su secuencia.
BEGIN;

ALTER TABLE enlaces_publicos
    ADD COLUMN creado_por_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ADD COLUMN rol varchar(20) NOT NULL DEFAULT 'LECTURA',
    ADD COLUMN permite_descarga boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT chk_enlace_rol CHECK (rol IN ('LECTURA', 'ESCRITURA')),
    -- Subir solo tiene sentido en carpetas.
    ADD CONSTRAINT chk_enlace_escritura_carpeta CHECK (rol <> 'ESCRITURA' OR carpeta_id IS NOT NULL);
-- Un enlace por recurso: el dueño lo crea, lo modifica o lo revoca (DELETE).
CREATE UNIQUE INDEX ux_enlace_archivo ON enlaces_publicos (archivo_id) WHERE archivo_id IS NOT NULL;
CREATE UNIQUE INDEX ux_enlace_carpeta ON enlaces_publicos (carpeta_id) WHERE carpeta_id IS NOT NULL;

ALTER TABLE permisos_recurso
    ADD COLUMN permite_descarga boolean NOT NULL DEFAULT true,
    -- Permiso obtenido al abrir un enlace con sesión: desaparece al revocar el enlace.
    ADD COLUMN enlace_id uuid REFERENCES enlaces_publicos(id) ON DELETE CASCADE,
    ADD COLUMN fecha_creacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT chk_tipo_permiso CHECK (tipo_permiso IN ('LECTURA', 'ESCRITURA')),
    ADD CONSTRAINT chk_permiso_escritura_carpeta CHECK (tipo_permiso <> 'ESCRITURA' OR carpeta_id IS NOT NULL);
CREATE UNIQUE INDEX ux_permiso_archivo_usuario ON permisos_recurso (archivo_id, usuario_id) WHERE archivo_id IS NOT NULL;
CREATE UNIQUE INDEX ux_permiso_carpeta_usuario ON permisos_recurso (carpeta_id, usuario_id) WHERE carpeta_id IS NOT NULL;
CREATE INDEX idx_permisos_recurso_usuario ON permisos_recurso (usuario_id);

COMMIT;
