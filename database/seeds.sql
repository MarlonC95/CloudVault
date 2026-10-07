INSERT INTO planes (id, nombre, limite_almacenamiento_bytes, precio, esta_activo) VALUES
(1, 'Gratuito / Básico', 16106127360, 0.00, TRUE),           -- 15 GB
(2, 'Pro PaaS / Premium', 107374182400, 29.00, TRUE),        -- 100 GB
(3, 'Empresarial / Platinum', 1099511627776, 99.00, TRUE)   -- 1 TB
ON CONFLICT (id) DO NOTHING;

-- Sincronizar secuencia del ID de planes
SELECT setval('planes_id_seq', (SELECT MAX(id) FROM planes));