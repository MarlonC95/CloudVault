-- Métodos de pago simulados (tarjetas de crédito/débito) por organización.
-- APLICADO en Railway por el DBA el 2026-11-12; este script refleja la tabla desplegada
-- (columnas, restricciones e índices leídos de la BD real) y el test runner lo carga.
-- Solo guarda datos no sensibles: el número completo y el CVV nunca llegan a la BD.
-- El límite de 2 tarjetas por organización y actualizado_en los mantiene el backend.
-- El backend se conecta como postgres (dueño de las tablas): no hace falta GRANT.
BEGIN;

CREATE TABLE metodos_pago (
    id uuid PRIMARY KEY,
    organizacion_id uuid NOT NULL REFERENCES organizaciones(id) ON DELETE CASCADE,
    titular varchar(150) NOT NULL,
    marca varchar(50) NOT NULL,
    tipo varchar(20) NOT NULL,
    ultimos_4 varchar(4) NOT NULL,
    mes_vencimiento smallint NOT NULL,
    anio_vencimiento smallint NOT NULL,
    es_predeterminada boolean NOT NULL DEFAULT false,
    creado_en timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_metodos_pago_tipo CHECK (tipo IN ('CREDITO', 'DEBITO')),
    CONSTRAINT chk_metodos_pago_ultimos_4 CHECK (ultimos_4 ~ '^[0-9]{4}$'),
    CONSTRAINT chk_metodos_pago_mes CHECK (mes_vencimiento BETWEEN 1 AND 12)
);
CREATE INDEX idx_metodos_pago_organizacion ON metodos_pago (organizacion_id);
-- Como mucho una tarjeta predeterminada por organización.
CREATE UNIQUE INDEX idx_unica_tarjeta_predeterminada ON metodos_pago (organizacion_id)
    WHERE es_predeterminada = true;

COMMIT;
