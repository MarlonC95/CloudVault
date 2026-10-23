-- 1. Función para actualizar fecha de modificación
CREATE OR REPLACE FUNCTION trigger_actualizar_marca_tiempo()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers de actualización
DROP TRIGGER IF EXISTS trg_actualizar_organizaciones ON organizaciones;
CREATE TRIGGER trg_actualizar_organizaciones
    BEFORE UPDATE ON organizaciones
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

DROP TRIGGER IF EXISTS trg_actualizar_usuarios ON usuarios;
CREATE TRIGGER trg_actualizar_usuarios
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

DROP TRIGGER IF EXISTS trg_actualizar_carpetas ON carpetas;
CREATE TRIGGER trg_actualizar_carpetas
    BEFORE UPDATE ON carpetas
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

DROP TRIGGER IF EXISTS trg_actualizar_archivos ON archivos;
CREATE TRIGGER trg_actualizar_archivos
    BEFORE UPDATE ON archivos
    FOR EACH ROW EXECUTE FUNCTION trigger_actualizar_marca_tiempo();

-- 2. Función para recalcular automáticamente el almacenamiento de la organización
CREATE OR REPLACE FUNCTION trigger_ajustar_cuota_almacenamiento()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cuota_archivos ON archivos;
CREATE TRIGGER trg_cuota_archivos
    AFTER INSERT OR UPDATE OR DELETE ON archivos
    FOR EACH ROW EXECUTE FUNCTION trigger_ajustar_cuota_almacenamiento();