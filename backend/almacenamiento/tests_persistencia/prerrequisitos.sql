-- EXCLUSIVAMENTE para el clúster desechable de ejecutar.py.
-- No es una migración ni una autorización para aplicarlo al entorno compartido.
CREATE EXTENSION btree_gist;
CREATE ROLE lector_cloudvault NOLOGIN;
CREATE FUNCTION trigger_actualizar_marca_tiempo() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN NEW.actualizado_en = clock_timestamp(); RETURN NEW; END; $$;
