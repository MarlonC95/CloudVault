-- DDL reconstruido del esquema `public` desplegado (solo lectura del catálogo).
-- Fuente de verdad para pruebas y para dev_pruebas. Sin datos ni credenciales.
-- Portable: gen_random_uuid() (PostgreSQL >= 13) reemplaza uuid_generate_v4() para no depender de uuid-ossp.

-- Tablas: archivos, carpetas, enlaces_publicos, historial_pagos, intentos_publicacion, logs_auditoria, miembros_organizacion, organizaciones, permisos_recurso, planes, sesiones_carga, suscripciones, trabajos_mantenimiento, usuarios
CREATE TABLE IF NOT EXISTS "archivos" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "organizacion_id" uuid,
    "carpeta_id" uuid,
    "propietario_id" uuid NOT NULL,
    "nombre" character varying(255) NOT NULL,
    "clave_s3" character varying(500) NOT NULL,
    "tamano_bytes" bigint NOT NULL,
    "tipo_mime" character varying(100) NOT NULL,
    "en_papelera" boolean NOT NULL DEFAULT false,
    "fecha_papelera" timestamp with time zone,
    "fecha_subida" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actualizado_en" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "carpetas" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "organizacion_id" uuid,
    "carpeta_padre_id" uuid,
    "nombre" character varying(255) NOT NULL,
    "en_papelera" boolean NOT NULL DEFAULT false,
    "fecha_papelera" timestamp with time zone,
    "fecha_creacion" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "enlaces_publicos" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "token_random" character varying(255) NOT NULL,
    "archivo_id" uuid,
    "carpeta_id" uuid,
    "contrasena_hash" character varying(255),
    "fecha_expiracion" timestamp with time zone,
    "fecha_creacion" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "historial_pagos" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "suscripcion_id" uuid NOT NULL,
    "monto" numeric(10,2) NOT NULL,
    "estado" character varying(50) NOT NULL,
    "referencia_transaccion" character varying(255) NOT NULL,
    "fecha_pago" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "intentos_publicacion" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "sesion_id" uuid NOT NULL,
    "clave_final" character varying(1024) NOT NULL,
    "etag_origen" character varying(255) NOT NULL,
    "version_origen" character varying(255),
    "checksum_origen" character varying(64),
    "etag_final" character varying(255),
    "version_final" character varying(255),
    "estado" character varying(10) NOT NULL DEFAULT 'PREPARED'::character varying,
    "creado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actualizado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "logs_auditoria" (
    "id" BIGSERIAL,
    "organizacion_id" uuid,
    "usuario_id" uuid,
    "accion" character varying(100) NOT NULL,
    "ip_origen" character varying(45),
    "detalles" jsonb,
    "fecha_evento" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "miembros_organizacion" (
    "id" BIGSERIAL,
    "organizacion_id" uuid NOT NULL,
    "usuario_id" uuid NOT NULL,
    "nivel_rol" smallint NOT NULL,
    "fecha_union" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "organizaciones" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "nombre" character varying(150) NOT NULL,
    "almacenamiento_usado_bytes" bigint NOT NULL DEFAULT 0,
    "fecha_creacion" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "slug" character varying(150),
    "actualizado_en" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "permisos_recurso" (
    "id" BIGSERIAL,
    "archivo_id" uuid,
    "carpeta_id" uuid,
    "usuario_id" uuid NOT NULL,
    "tipo_permiso" character varying(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS "planes" (
    "id" SERIAL,
    "nombre" character varying(100) NOT NULL,
    "limite_almacenamiento_bytes" bigint NOT NULL,
    "precio" numeric(10,2) NOT NULL DEFAULT 0.00,
    "esta_activo" boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS "sesiones_carga" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "archivo_id" uuid NOT NULL,
    "solicitante_id" uuid NOT NULL,
    "organizacion_id" uuid NOT NULL,
    "carpeta_id" uuid,
    "nombre" character varying(255) NOT NULL,
    "tipo_mime" character varying(100) NOT NULL,
    "tamano_bytes" bigint NOT NULL,
    "checksum_sha256" character varying(64),
    "etag" character varying(255),
    "clave_temporal" character varying(1024) NOT NULL,
    "expira_en" timestamp with time zone NOT NULL,
    "estado" character varying(10) NOT NULL DEFAULT 'PENDING'::character varying,
    "resultado_confirmacion" jsonb,
    "creado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actualizado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "suscripciones" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "organizacion_id" uuid NOT NULL,
    "plan_id" integer NOT NULL,
    "estado" character varying(50) NOT NULL DEFAULT 'ACTIVE'::character varying,
    "periodo_inicio" timestamp with time zone NOT NULL,
    "periodo_fin" timestamp with time zone NOT NULL,
    "auto_renovar" boolean NOT NULL DEFAULT true,
    "intervalo" character varying(20) NOT NULL DEFAULT 'MONTHLY'::character varying
);
CREATE TABLE IF NOT EXISTS "trabajos_mantenimiento" (
    "sesion_id" uuid NOT NULL,
    "cancelar" boolean NOT NULL DEFAULT false,
    "copia_concluida" boolean NOT NULL DEFAULT false,
    "estado" character varying(16) NOT NULL DEFAULT 'PENDING'::character varying,
    "intentos" bigint NOT NULL DEFAULT 0,
    "fallos_consecutivos" integer NOT NULL DEFAULT 0,
    "proximo_intento" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "causa" character varying(32) NOT NULL DEFAULT ''::character varying,
    "verificado_en" timestamp with time zone,
    "creado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actualizado_en" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "usuarios" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "correo_electronico" character varying(255) NOT NULL,
    "contrasena_hash" character varying(255) NOT NULL,
    "nombre_completo" character varying(150) NOT NULL,
    "palabra_secreta_hash" character varying(255) NOT NULL,
    "esta_activo" boolean NOT NULL DEFAULT true,
    "fecha_creacion" timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "totp_secret" character varying(64) DEFAULT NULL::character varying,
    "is_2fa_enabled" boolean NOT NULL DEFAULT false,
    "actualizado_en" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE "archivos" ADD CONSTRAINT "archivos_pkey" PRIMARY KEY (id);
ALTER TABLE "carpetas" ADD CONSTRAINT "carpetas_pkey" PRIMARY KEY (id);
ALTER TABLE "enlaces_publicos" ADD CONSTRAINT "enlaces_publicos_pkey" PRIMARY KEY (id);
ALTER TABLE "historial_pagos" ADD CONSTRAINT "historial_pagos_pkey" PRIMARY KEY (id);
ALTER TABLE "intentos_publicacion" ADD CONSTRAINT "intentos_publicacion_pkey" PRIMARY KEY (id);
ALTER TABLE "logs_auditoria" ADD CONSTRAINT "logs_auditoria_pkey" PRIMARY KEY (id);
ALTER TABLE "miembros_organizacion" ADD CONSTRAINT "miembros_organizacion_pkey" PRIMARY KEY (id);
ALTER TABLE "organizaciones" ADD CONSTRAINT "organizaciones_pkey" PRIMARY KEY (id);
ALTER TABLE "permisos_recurso" ADD CONSTRAINT "permisos_recurso_pkey" PRIMARY KEY (id);
ALTER TABLE "planes" ADD CONSTRAINT "planes_pkey" PRIMARY KEY (id);
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_pkey" PRIMARY KEY (id);
ALTER TABLE "suscripciones" ADD CONSTRAINT "suscripciones_pkey" PRIMARY KEY (id);
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_pkey" PRIMARY KEY (sesion_id);
ALTER TABLE "usuarios" ADD CONSTRAINT "usuarios_pkey" PRIMARY KEY (id);
ALTER TABLE "archivos" ADD CONSTRAINT "archivos_clave_s3_key" UNIQUE (clave_s3);
ALTER TABLE "enlaces_publicos" ADD CONSTRAINT "enlaces_publicos_token_random_key" UNIQUE (token_random);
ALTER TABLE "intentos_publicacion" ADD CONSTRAINT "intentos_publicacion_clave_final_key" UNIQUE (clave_final);
ALTER TABLE "intentos_publicacion" ADD CONSTRAINT "intentos_publicacion_sesion_id_key" UNIQUE (sesion_id);
ALTER TABLE "miembros_organizacion" ADD CONSTRAINT "uq_miembro_org" UNIQUE (organizacion_id, usuario_id);
ALTER TABLE "organizaciones" ADD CONSTRAINT "organizaciones_slug_key" UNIQUE (slug);
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_archivo_id_key" UNIQUE (archivo_id);
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_clave_temporal_key" UNIQUE (clave_temporal);
ALTER TABLE "usuarios" ADD CONSTRAINT "usuarios_correo_electronico_key" UNIQUE (correo_electronico);
ALTER TABLE "enlaces_publicos" ADD CONSTRAINT "chk_enlace_recurso_exclusivo" CHECK ((((archivo_id IS NOT NULL) AND (carpeta_id IS NULL)) OR ((archivo_id IS NULL) AND (carpeta_id IS NOT NULL))));
ALTER TABLE "intentos_publicacion" ADD CONSTRAINT "intentos_publicacion_estado_check" CHECK (((estado)::text = ANY ((ARRAY['PREPARED'::character varying, 'PUBLISHED'::character varying, 'ABANDONED'::character varying, 'CLEANED'::character varying])::text[])));
ALTER TABLE "miembros_organizacion" ADD CONSTRAINT "miembros_organizacion_nivel_rol_check" CHECK ((nivel_rol = ANY (ARRAY[0, 1, 2, 3])));
ALTER TABLE "permisos_recurso" ADD CONSTRAINT "chk_recurso_exclusivo" CHECK ((((archivo_id IS NOT NULL) AND (carpeta_id IS NULL)) OR ((archivo_id IS NULL) AND (carpeta_id IS NOT NULL))));
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_check" CHECK ((expira_en > creado_en));
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_checksum_sha256_check" CHECK (((checksum_sha256 IS NULL) OR ((checksum_sha256)::text ~ '^[0-9a-f]{64}$'::text)));
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_estado_check" CHECK (((estado)::text = ANY ((ARRAY['PENDING'::character varying, 'CONFIRMED'::character varying, 'CANCELED'::character varying, 'EXPIRED'::character varying])::text[])));
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_tamano_bytes_check" CHECK ((tamano_bytes >= 0));
ALTER TABLE "suscripciones" ADD CONSTRAINT "suscripciones_intervalo_check" CHECK (((intervalo)::text = ANY ((ARRAY['MONTHLY'::character varying, 'YEARLY'::character varying])::text[])));
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_causa_check" CHECK (((causa)::text = ANY ((ARRAY[''::character varying, 'URL_VIGENTE'::character varying, 'COPY_AMBIGUO'::character varying, 'REFERENCIADO'::character varying, 'DEPENDENCIA'::character varying, 'S3'::character varying, 'SQL'::character varying, 'INTEGRIDAD'::character varying, 'OCUPADO'::character varying, 'RECUPERACION'::character varying, 'ERROR'::character varying])::text[])));
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_check" CHECK ((((estado)::text <> 'VERIFIED'::text) OR (verificado_en IS NOT NULL)));
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_estado_check" CHECK (((estado)::text = ANY ((ARRAY['PENDING'::character varying, 'RETRY'::character varying, 'RECONCILE'::character varying, 'VERIFIED'::character varying])::text[])));
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_fallos_consecutivos_check" CHECK ((fallos_consecutivos >= 0));
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_intentos_check" CHECK ((intentos >= 0));
ALTER TABLE "archivos" ADD CONSTRAINT "archivos_carpeta_id_fkey" FOREIGN KEY (carpeta_id) REFERENCES carpetas(id) ON DELETE SET NULL;
ALTER TABLE "archivos" ADD CONSTRAINT "archivos_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "archivos" ADD CONSTRAINT "archivos_propietario_id_fkey" FOREIGN KEY (propietario_id) REFERENCES usuarios(id) ON DELETE RESTRICT;
ALTER TABLE "carpetas" ADD CONSTRAINT "carpetas_carpeta_padre_id_fkey" FOREIGN KEY (carpeta_padre_id) REFERENCES carpetas(id) ON DELETE CASCADE;
ALTER TABLE "carpetas" ADD CONSTRAINT "carpetas_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "enlaces_publicos" ADD CONSTRAINT "enlaces_publicos_archivo_id_fkey" FOREIGN KEY (archivo_id) REFERENCES archivos(id) ON DELETE CASCADE;
ALTER TABLE "enlaces_publicos" ADD CONSTRAINT "enlaces_publicos_carpeta_id_fkey" FOREIGN KEY (carpeta_id) REFERENCES carpetas(id) ON DELETE CASCADE;
ALTER TABLE "historial_pagos" ADD CONSTRAINT "historial_pagos_suscripcion_id_fkey" FOREIGN KEY (suscripcion_id) REFERENCES suscripciones(id) ON DELETE CASCADE;
ALTER TABLE "intentos_publicacion" ADD CONSTRAINT "intentos_publicacion_sesion_id_fkey" FOREIGN KEY (sesion_id) REFERENCES sesiones_carga(id) ON DELETE RESTRICT;
ALTER TABLE "logs_auditoria" ADD CONSTRAINT "logs_auditoria_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "logs_auditoria" ADD CONSTRAINT "logs_auditoria_usuario_id_fkey" FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;
ALTER TABLE "miembros_organizacion" ADD CONSTRAINT "miembros_organizacion_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "miembros_organizacion" ADD CONSTRAINT "miembros_organizacion_usuario_id_fkey" FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
ALTER TABLE "permisos_recurso" ADD CONSTRAINT "permisos_recurso_archivo_id_fkey" FOREIGN KEY (archivo_id) REFERENCES archivos(id) ON DELETE CASCADE;
ALTER TABLE "permisos_recurso" ADD CONSTRAINT "permisos_recurso_carpeta_id_fkey" FOREIGN KEY (carpeta_id) REFERENCES carpetas(id) ON DELETE CASCADE;
ALTER TABLE "permisos_recurso" ADD CONSTRAINT "permisos_recurso_usuario_id_fkey" FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_carpeta_id_fkey" FOREIGN KEY (carpeta_id) REFERENCES carpetas(id) ON DELETE SET NULL;
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "sesiones_carga" ADD CONSTRAINT "sesiones_carga_solicitante_id_fkey" FOREIGN KEY (solicitante_id) REFERENCES usuarios(id) ON DELETE RESTRICT;
ALTER TABLE "suscripciones" ADD CONSTRAINT "suscripciones_organizacion_id_fkey" FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id) ON DELETE CASCADE;
ALTER TABLE "suscripciones" ADD CONSTRAINT "suscripciones_plan_id_fkey" FOREIGN KEY (plan_id) REFERENCES planes(id) ON DELETE RESTRICT;
ALTER TABLE "trabajos_mantenimiento" ADD CONSTRAINT "trabajos_mantenimiento_sesion_id_fkey" FOREIGN KEY (sesion_id) REFERENCES sesiones_carga(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_archivos_carpeta ON archivos USING btree (carpeta_id);
CREATE INDEX IF NOT EXISTS idx_archivos_org ON archivos USING btree (organizacion_id);
CREATE INDEX IF NOT EXISTS idx_archivos_papelera ON archivos USING btree (en_papelera, fecha_papelera);
CREATE INDEX IF NOT EXISTS idx_carpetas_org ON carpetas USING btree (organizacion_id);
CREATE INDEX IF NOT EXISTS idx_carpetas_padre ON carpetas USING btree (carpeta_padre_id);
CREATE INDEX IF NOT EXISTS idx_carpetas_papelera ON carpetas USING btree (en_papelera, fecha_papelera);
CREATE INDEX IF NOT EXISTS idx_logs_auditoria_org ON logs_auditoria USING btree (organizacion_id, fecha_evento DESC);
CREATE INDEX IF NOT EXISTS idx_miembros_org ON miembros_organizacion USING btree (organizacion_id, usuario_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_cuota_pendiente ON sesiones_carga USING btree (organizacion_id, expira_en) WHERE ((estado)::text = 'PENDING'::text);
CREATE INDEX IF NOT EXISTS idx_sesiones_solicitante ON sesiones_carga USING btree (solicitante_id);
CREATE INDEX IF NOT EXISTS idx_mantenimiento_proximo ON trabajos_mantenimiento USING btree (proximo_intento, sesion_id);

CREATE OR REPLACE FUNCTION trigger_actualizar_marca_tiempo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    BEGIN
        NEW.actualizado_en = CURRENT_TIMESTAMP;
    EXCEPTION
        WHEN undefined_column THEN
            -- Si la tabla no tiene la columna actualizado_en, no hace nada y permite el UPDATE
            NULL;
    END;
    RETURN NEW;
END;
$function$;
CREATE OR REPLACE FUNCTION trigger_ajustar_cuota_almacenamiento()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.organizacion_id IS NOT NULL AND NEW.en_papelera = FALSE THEN
            UPDATE organizaciones 
            SET almacenamiento_usado_bytes = almacenamiento_usado_bytes + NEW.tamano_bytes
            WHERE id = NEW.organizacion_id;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.organizacion_id IS NOT NULL AND OLD.en_papelera = FALSE THEN
            UPDATE organizaciones 
            SET almacenamiento_usado_bytes = GREATEST(0, almacenamiento_usado_bytes - OLD.tamano_bytes)
            WHERE id = OLD.organizacion_id;
        END IF;
    ELSIF TG_OP = 'UPDATE' THEN
        -- Si cambió de papelera (se envió o se restauró) o cambió de tamaño
        IF OLD.organizacion_id IS NOT NULL THEN
            IF OLD.en_papelera = FALSE AND NEW.en_papelera = TRUE THEN
                UPDATE organizaciones 
                SET almacenamiento_usado_bytes = GREATEST(0, almacenamiento_usado_bytes - OLD.tamano_bytes)
                WHERE id = OLD.organizacion_id;
            ELSIF OLD.en_papelera = TRUE AND NEW.en_papelera = FALSE THEN
                UPDATE organizaciones 
                SET almacenamiento_usado_bytes = almacenamiento_usado_bytes + NEW.tamano_bytes
                WHERE id = NEW.organizacion_id;
            ELSIF OLD.en_papelera = FALSE AND NEW.en_papelera = FALSE AND OLD.tamano_bytes <> NEW.tamano_bytes THEN
                UPDATE organizaciones 
                SET almacenamiento_usado_bytes = GREATEST(0, almacenamiento_usado_bytes - OLD.tamano_bytes + NEW.tamano_bytes)
                WHERE id = NEW.organizacion_id;
            END IF;
        END IF;
    END IF;
    RETURN NULL;
END;
$function$;
CREATE OR REPLACE TRIGGER trg_actualizar_archivos BEFORE UPDATE ON archivos FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_cuota_archivos AFTER INSERT OR DELETE OR UPDATE ON archivos FOR EACH ROW EXECUTE FUNCTION trigger_ajustar_cuota_almacenamiento();
CREATE OR REPLACE TRIGGER trg_actualizar_carpetas BEFORE UPDATE ON carpetas FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_actualizar_intentos_publicacion BEFORE UPDATE ON intentos_publicacion FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_actualizar_organizaciones BEFORE UPDATE ON organizaciones FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_actualizar_sesiones_carga BEFORE UPDATE ON sesiones_carga FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_actualizar_trabajos_mantenimiento BEFORE UPDATE ON trabajos_mantenimiento FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();
CREATE OR REPLACE TRIGGER trg_actualizar_usuarios BEFORE UPDATE ON usuarios FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

-- Semillas de planes (copiadas de la tabla planes desplegada)
INSERT INTO planes (id, nombre, limite_almacenamiento_bytes, precio, esta_activo) VALUES (1, 'Gratuito / Básico', 16106127360, 0.00, TRUE) ON CONFLICT (id) DO NOTHING;
INSERT INTO planes (id, nombre, limite_almacenamiento_bytes, precio, esta_activo) VALUES (2, 'Pro PaaS / Premium', 107374182400, 29.00, TRUE) ON CONFLICT (id) DO NOTHING;
INSERT INTO planes (id, nombre, limite_almacenamiento_bytes, precio, esta_activo) VALUES (3, 'Empresarial / Platinum', 1099511627776, 99.00, TRUE) ON CONFLICT (id) DO NOTHING;
SELECT setval(pg_get_serial_sequence('planes','id'), (SELECT MAX(id) FROM planes));
