-- CloudVault: preparar el esquema public para que la aplicación use las tablas de Marlon.
--
-- Ejecutar UNA vez en Railway, conectado como el dueño de las tablas (postgres).
-- ANTES: hacer backup de public.
-- Reemplazar USUARIO_APP por el usuario de la DATABASE_URL del backend (el mismo de dev_pruebas)
-- o por un usuario dedicado para la aplicación.
-- Todo va en una transacción: si algo falla, no se aplica nada.

BEGIN;

-- 1. Eliminar las 13 tablas que creó un `manage.py migrate` de una versión antigua del backend.
--    El sistema actual NO las usa (sus modelos son managed = False sobre las tablas de Marlon).
--    Todas están vacías salvo auth_permission, que Django rellena solo al migrar.
DROP TABLE IF EXISTS
    accounts_user_user_permissions, accounts_user_groups, accounts_user,
    storage_filemetadata, storage_folder,
    subscriptions_subscription, subscriptions_plan,
    auth_group_permissions, auth_permission, auth_group,
    django_session, django_content_type, django_migrations;

-- 2. Permisos mínimos para la aplicación (hoy ese usuario solo puede leer public).
GRANT USAGE ON SCHEMA public TO "USUARIO_APP";
GRANT SELECT ON planes TO "USUARIO_APP";
GRANT SELECT, INSERT, UPDATE, DELETE ON
    usuarios, organizaciones, miembros_organizacion, suscripciones, historial_pagos,
    carpetas, archivos, permisos_recurso, enlaces_publicos, logs_auditoria,
    sesiones_carga, intentos_publicacion, trabajos_mantenimiento
    TO "USUARIO_APP";
GRANT USAGE, SELECT ON SEQUENCE
    logs_auditoria_id_seq, miembros_organizacion_id_seq, permisos_recurso_id_seq
    TO "USUARIO_APP";

-- 3. Datos legados: toda organización necesita una suscripción activa para tener cuota.
--    Las que no tienen ninguna reciben el plan Gratuito (15 GB), igual que en el registro.
INSERT INTO suscripciones (organizacion_id, plan_id, estado, intervalo, periodo_inicio, periodo_fin, auto_renovar)
SELECT o.id, 1, 'ACTIVE', 'MONTHLY', now(), now() + interval '10 years', true
FROM organizaciones o
WHERE NOT EXISTS (
    SELECT 1 FROM suscripciones s WHERE s.organizacion_id = o.id AND s.estado = 'ACTIVE'
);
--    Los usuarios sin organización NO necesitan nada aquí: el backend les crea su
--    espacio personal (organización + membresía + Gratuito) en su primera petición.

COMMIT;

-- 4. Verificación (debe devolver 14 tablas y permisos de escritura en true).
SELECT count(*) AS tablas_public
FROM pg_class
WHERE relnamespace = 'public'::regnamespace AND relkind = 'r';

SELECT t AS tabla,
       has_table_privilege('USUARIO_APP', 'public.' || t, 'INSERT') AS puede_escribir
FROM unnest(ARRAY['usuarios', 'organizaciones', 'carpetas', 'archivos', 'suscripciones',
                  'sesiones_carga', 'trabajos_mantenimiento']) AS t;
