-- Industrial IoT Demo — Snowflake / DuckDB Schema
-- Bronze → Silver → Gold layer definitions
-- Source of truth: contracts/interface-contracts.md (C9–C12)
-- All tables use snake_case. Timestamps are UTC.

-- ─────────────────────────────────────────────
-- BRONZE LAYER — raw ingestion, no transformation
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bronze_sensor_readings (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mqtt_topic          VARCHAR NOT NULL,
    raw_payload         VARCHAR NOT NULL,       -- full JSON string as received
    timestamp           TIMESTAMP NOT NULL,
    plant_id            VARCHAR,
    oven_id             VARCHAR,
    sensor_type         VARCHAR,
    value               DOUBLE,
    unit                VARCHAR,
    quality             VARCHAR,
    order_id            VARCHAR                 -- null if no active order
);

CREATE TABLE IF NOT EXISTS bronze_mes_events (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type          VARCHAR NOT NULL,       -- order_started | order_confirmed | quality_check
    raw_payload         VARCHAR NOT NULL,
    order_id            VARCHAR,
    operator_id         VARCHAR,
    event_time          TIMESTAMP,
    payload_json        VARCHAR                 -- full event JSON
);

CREATE TABLE IF NOT EXISTS bronze_sap_production_orders (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_id            VARCHAR NOT NULL,
    material_id         VARCHAR,
    plant               VARCHAR,
    planned_start       TIMESTAMP,
    planned_end         TIMESTAMP,
    standard_cycle_minutes INT,
    status              VARCHAR,
    routing_id          VARCHAR,
    raw_payload         VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze_sap_material_master (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    material_id         VARCHAR NOT NULL,
    description         VARCHAR,
    insulation_class    VARCHAR,
    target_moisture_ppm DOUBLE,
    standard_cycle_minutes INT,
    max_temperature_degC DOUBLE,
    min_vacuum_mbar     DOUBLE,
    raw_payload         VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze_sap_goods_movements (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    document_number     VARCHAR,
    order_id            VARCHAR,
    material_id         VARCHAR,
    movement_type       VARCHAR,
    quantity            DOUBLE,
    unit                VARCHAR,
    posting_date        DATE,
    storage_location    VARCHAR,
    posted_at           TIMESTAMP,
    raw_payload         VARCHAR
);

-- ─────────────────────────────────────────────
-- SILVER LAYER — cleaned, typed, deduplicated
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS silver_sensor_readings (
    timestamp           TIMESTAMP NOT NULL,
    plant_id            VARCHAR NOT NULL,
    oven_id             VARCHAR NOT NULL,
    sensor_type         VARCHAR NOT NULL,
    value               DOUBLE NOT NULL,
    unit                VARCHAR NOT NULL,
    quality             VARCHAR NOT NULL,       -- Good | Bad | Uncertain
    order_id            VARCHAR,
    -- derived
    is_good_quality     BOOLEAN GENERATED ALWAYS AS (quality = 'Good'),
    PRIMARY KEY (timestamp, oven_id, sensor_type)
);

CREATE TABLE IF NOT EXISTS silver_cycle_events (
    order_id            VARCHAR NOT NULL,
    event_type          VARCHAR NOT NULL,
    event_time          TIMESTAMP NOT NULL,
    operator_id         VARCHAR,
    quality_check_passed BOOLEAN,
    PRIMARY KEY (order_id, event_type)
);

CREATE TABLE IF NOT EXISTS silver_production_orders (
    order_id            VARCHAR PRIMARY KEY,
    material_id         VARCHAR NOT NULL,
    plant               VARCHAR NOT NULL,
    planned_start       TIMESTAMP,
    planned_end         TIMESTAMP,
    standard_cycle_minutes INT,
    status              VARCHAR,
    routing_id          VARCHAR,
    sap_confirmation_number VARCHAR,
    last_updated        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver_material_master (
    material_id         VARCHAR PRIMARY KEY,
    description         VARCHAR,
    insulation_class    VARCHAR,
    target_moisture_ppm DOUBLE,
    standard_cycle_minutes INT,
    max_temperature_degC DOUBLE,
    min_vacuum_mbar     DOUBLE,
    last_updated        TIMESTAMP
);

-- ─────────────────────────────────────────────
-- GOLD LAYER — analytical, joined, aggregated
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gold_cycle_summary (
    -- identity
    order_id                    VARCHAR PRIMARY KEY,
    material_id                 VARCHAR NOT NULL,
    plant                       VARCHAR NOT NULL,
    -- timing
    cycle_start                 TIMESTAMP,
    cycle_end                   TIMESTAMP,
    actual_duration_minutes     INT,
    standard_duration_minutes   INT,
    delta_minutes               INT,            -- actual - standard (negative = faster)
    -- sensor peaks
    peak_temperature_degC       DOUBLE,
    min_vacuum_mbar             DOUBLE,
    final_moisture_ppm          DOUBLE,
    avg_moisture_ppm            DOUBLE,
    -- spec compliance
    target_moisture_ppm         DOUBLE,
    moisture_spec_met           BOOLEAN,        -- final_moisture_ppm <= target_moisture_ppm
    max_temperature_limit_degC  DOUBLE,
    temperature_limit_met       BOOLEAN,
    -- outcome
    quality_check_passed        BOOLEAN,
    operator_id                 VARCHAR,
    sap_confirmation_number     VARCHAR,
    -- metadata
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Useful analytical views

CREATE VIEW IF NOT EXISTS v_cycle_efficiency AS
SELECT
    material_id,
    COUNT(*) AS total_cycles,
    AVG(actual_duration_minutes) AS avg_actual_minutes,
    AVG(standard_duration_minutes) AS avg_standard_minutes,
    AVG(delta_minutes) AS avg_delta_minutes,
    SUM(CASE WHEN delta_minutes < 0 THEN 1 ELSE 0 END) AS cycles_faster_than_standard,
    SUM(CASE WHEN moisture_spec_met THEN 1 ELSE 0 END) AS cycles_meeting_moisture_spec,
    AVG(final_moisture_ppm) AS avg_final_moisture_ppm
FROM gold_cycle_summary
GROUP BY material_id;

CREATE VIEW IF NOT EXISTS v_recent_cycles AS
SELECT *
FROM gold_cycle_summary
ORDER BY cycle_start DESC
LIMIT 50;
