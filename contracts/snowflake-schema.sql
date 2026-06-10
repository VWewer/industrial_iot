-- Industrial IoT Demo -- Snowflake Schema
-- Bronze -> Silver -> Gold layer definitions
-- Source of truth: contracts/interface-contracts.md (C9-C12)
-- All tables use snake_case. Timestamps are UTC.
-- v1.2 2026-06-10: Gold fields aligned to C12 contract. Bronze/Silver aligned to DOMAIN-MODEL.md.
--   Key changes: cycle_start_time, cycle_end_time, spec_met (renamed), oven_id, material_description,
--   goods_movement_posted added. delta_minutes, actual_duration_minutes promoted to FLOAT.
--   max_temperature_degC / min_vacuum_mbar kept as nullable safety-threshold columns (requires C7
--   extension to populate -- not in current DOMAIN-MODEL MaterialMaster (see open items in WP5-BRIEF.md).

-- -----------------------------------------------------------
-- BRONZE LAYER -- raw ingestion, no transformation
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS bronze_sensor_readings (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mqtt_topic          VARCHAR NOT NULL,
    raw_payload         VARCHAR NOT NULL,       -- full JSON string as received
    reading_id          VARCHAR,               -- UUID from C1 payload
    timestamp_opc       TIMESTAMP NOT NULL,
    timestamp_mqtt      TIMESTAMP,
    plant_id            VARCHAR,
    oven_id             VARCHAR,
    sensor_type         VARCHAR,               -- temperature | vacuum | moisture
    value               DOUBLE,
    unit                VARCHAR,               -- degC | mbar | ppm
    quality             VARCHAR,               -- Good | Bad | Uncertain
    order_id            VARCHAR                -- null if no active order
);

CREATE TABLE IF NOT EXISTS bronze_mes_events (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_id            VARCHAR,               -- UUID from C10 payload
    event_type          VARCHAR NOT NULL,       -- cycle_started | cycle_confirmed | cycle_aborted |
                                               --   cycle_timeout | sap_confirmation_failed
    raw_payload         VARCHAR NOT NULL,       -- full JSON as received from WP3
    order_id            VARCHAR,
    oven_id             VARCHAR,
    operator_id         VARCHAR,
    event_time          TIMESTAMP,
    payload_json        VARCHAR                -- inner payload object as JSON string
);

-- C6 fields from WP4 ProductionOrders response (DOMAIN-MODEL 1.1)
CREATE TABLE IF NOT EXISTS bronze_sap_production_orders (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_id            VARCHAR NOT NULL,
    material_id         VARCHAR,
    plant               VARCHAR,
    oven_id             VARCHAR,
    planned_start       TIMESTAMP,
    planned_end         TIMESTAMP,
    standard_cycle_minutes INT,
    status              VARCHAR,               -- CREATED | RELEASED | IN_PROGRESS | CONFIRMED | ABORTED | CLOSED
    raw_payload         VARCHAR
);

-- C7 fields from WP4 Materials response (DOMAIN-MODEL 1.2)
-- NOTE: max_temperature_degC and min_vacuum_mbar are safety thresholds distinct from the
-- process setpoints (target_temperature_degC, target_vacuum_mbar). They are not currently
-- in DOMAIN-MODEL 1.2 or C7 -- these columns will be NULL until C7 is extended.
-- Tracked as open item in WP5-BRIEF.md.
CREATE TABLE IF NOT EXISTS bronze_sap_material_master (
    ingested_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    material_id             VARCHAR NOT NULL,
    material_description    VARCHAR,
    insulation_class        VARCHAR,           -- A | B | F | H
    target_moisture_ppm     DOUBLE,            -- drying endpoint
    standard_cycle_minutes  INT,
    max_cycle_minutes       INT,
    target_temperature_degC DOUBLE,            -- process setpoint
    target_vacuum_mbar      DOUBLE,            -- process setpoint
    weight_kg               DOUBLE,
    max_temperature_degC    DOUBLE,            -- safety limit (NULL until C7 extended)
    min_vacuum_mbar         DOUBLE,            -- safety limit (NULL until C7 extended)
    raw_payload             VARCHAR
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

-- -----------------------------------------------------------
-- SILVER LAYER -- cleaned, typed, deduplicated
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS silver_sensor_readings (
    reading_id          VARCHAR NOT NULL,
    timestamp_opc       TIMESTAMP NOT NULL,
    plant_id            VARCHAR NOT NULL,
    oven_id             VARCHAR NOT NULL,
    sensor_type         VARCHAR NOT NULL,      -- temperature | vacuum | moisture
    value               DOUBLE NOT NULL,
    unit                VARCHAR NOT NULL,
    quality             VARCHAR NOT NULL,       -- Good | Bad | Uncertain
    order_id            VARCHAR,
    PRIMARY KEY (reading_id)
);

CREATE TABLE IF NOT EXISTS silver_cycle_events (
    event_id            VARCHAR NOT NULL,
    order_id            VARCHAR NOT NULL,
    event_type          VARCHAR NOT NULL,      -- cycle_started | cycle_confirmed | ...
    event_time          TIMESTAMP NOT NULL,
    operator_id         VARCHAR,
    quality_check_passed BOOLEAN,
    sap_confirmation_number VARCHAR,           -- from cycle_confirmed payload
    goods_movement_document VARCHAR,           -- from cycle_confirmed payload
    PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS silver_production_orders (
    order_id            VARCHAR PRIMARY KEY,
    material_id         VARCHAR NOT NULL,
    plant               VARCHAR NOT NULL,
    oven_id             VARCHAR,
    planned_start       TIMESTAMP,
    planned_end         TIMESTAMP,
    standard_cycle_minutes INT,
    status              VARCHAR,
    last_updated        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver_material_master (
    material_id             VARCHAR PRIMARY KEY,
    material_description    VARCHAR,
    insulation_class        VARCHAR,
    target_moisture_ppm     DOUBLE,
    standard_cycle_minutes  INT,
    max_cycle_minutes       INT,
    target_temperature_degC DOUBLE,
    target_vacuum_mbar      DOUBLE,
    weight_kg               DOUBLE,
    max_temperature_degC    DOUBLE,            -- safety limit (NULL until C7 extended)
    min_vacuum_mbar         DOUBLE,            -- safety limit (NULL until C7 extended)
    last_updated            TIMESTAMP
);

-- -----------------------------------------------------------
-- GOLD LAYER -- analytical, joined, aggregated (C12)
-- -----------------------------------------------------------
-- Field names match interface-contracts.md C12 exactly.
-- Extra analytics columns (avg_moisture_ppm, max_temperature_limit_degC,
-- temperature_limit_met) are beyond C12 and populated only once C7 is extended.

CREATE TABLE IF NOT EXISTS gold_cycle_summary (
    -- identity (C12)
    order_id                    VARCHAR PRIMARY KEY,
    material_id                 VARCHAR NOT NULL,
    material_description        VARCHAR,
    plant                       VARCHAR NOT NULL,
    oven_id                     VARCHAR NOT NULL,
    -- timing (C12)
    cycle_start_time            TIMESTAMP,
    cycle_end_time              TIMESTAMP,
    actual_duration_minutes     FLOAT,
    standard_cycle_minutes      INT,
    delta_minutes               FLOAT,         -- actual - standard (negative = faster than plan)
    -- sensor peaks (C12)
    peak_temperature_degC       DOUBLE,
    min_vacuum_mbar             DOUBLE,
    final_moisture_ppm          DOUBLE,
    target_moisture_ppm         DOUBLE,
    -- spec compliance (C12)
    spec_met                    BOOLEAN,       -- final_moisture_ppm < target_moisture_ppm
    quality_check_passed        BOOLEAN,
    -- outcome (C12)
    operator_id                 VARCHAR,
    sap_confirmation_number     VARCHAR,
    goods_movement_posted       BOOLEAN DEFAULT FALSE,
    -- extended analytics (beyond C12 -- populated when C7 extended for safety thresholds)
    avg_moisture_ppm            DOUBLE,
    max_temperature_limit_degC  DOUBLE,        -- from silver_material_master.max_temperature_degC
    temperature_limit_met       BOOLEAN,       -- peak_temperature_degC <= max_temperature_limit_degC
    -- metadata
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------
-- ANALYTICAL VIEWS
-- -----------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_cycle_efficiency AS
SELECT
    material_id,
    material_description,
    COUNT(*) AS total_cycles,
    AVG(actual_duration_minutes) AS avg_actual_minutes,
    AVG(standard_cycle_minutes) AS avg_standard_minutes,
    AVG(delta_minutes) AS avg_delta_minutes,
    SUM(CASE WHEN delta_minutes < 0 THEN 1 ELSE 0 END) AS cycles_faster_than_standard,
    SUM(CASE WHEN spec_met THEN 1 ELSE 0 END) AS cycles_meeting_spec,
    AVG(final_moisture_ppm) AS avg_final_moisture_ppm
FROM gold_cycle_summary
GROUP BY material_id, material_description;

CREATE VIEW IF NOT EXISTS v_recent_cycles AS
SELECT *
FROM gold_cycle_summary
ORDER BY cycle_start_time DESC
LIMIT 50;
