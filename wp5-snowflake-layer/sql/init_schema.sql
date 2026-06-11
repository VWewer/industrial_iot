-- WP5 Snowflake Schema -- Bronze -> Silver -> Gold
-- Source of truth: contracts/snowflake-schema.sql
-- Adapted for Snowflake DDL: CREATE OR REPLACE VIEW (Snowflake does not support IF NOT EXISTS on views)
-- Run once at service startup via SnowflakeClient.run_script()

-- -----------------------------------------------------------
-- BRONZE LAYER -- raw ingestion, no transformation
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS bronze_sensor_readings (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mqtt_topic          VARCHAR NOT NULL,
    raw_payload         VARCHAR NOT NULL,
    reading_id          VARCHAR,
    timestamp_opc       TIMESTAMP NOT NULL,
    timestamp_mqtt      TIMESTAMP,
    plant_id            VARCHAR,
    oven_id             VARCHAR,
    sensor_type         VARCHAR,
    value               DOUBLE,
    unit                VARCHAR,
    quality             VARCHAR,
    order_id            VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze_mes_events (
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_id            VARCHAR,
    event_type          VARCHAR NOT NULL,
    raw_payload         VARCHAR NOT NULL,
    order_id            VARCHAR,
    oven_id             VARCHAR,
    operator_id         VARCHAR,
    event_time          TIMESTAMP,
    payload_json        VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze_sap_production_orders (
    ingested_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_id                VARCHAR NOT NULL,
    material_id             VARCHAR,
    plant                   VARCHAR,
    oven_id                 VARCHAR,
    planned_start           TIMESTAMP,
    planned_end             TIMESTAMP,
    standard_cycle_minutes  INT,
    status                  VARCHAR,
    raw_payload             VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze_sap_material_master (
    ingested_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    material_id             VARCHAR NOT NULL,
    material_description    VARCHAR,
    insulation_class        VARCHAR,
    target_moisture_ppm     DOUBLE,
    standard_cycle_minutes  INT,
    max_cycle_minutes       INT,
    target_temperature_degC DOUBLE,
    target_vacuum_mbar      DOUBLE,
    weight_kg               DOUBLE,
    max_temperature_degC    DOUBLE,
    min_vacuum_mbar         DOUBLE,
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
    sensor_type         VARCHAR NOT NULL,
    value               DOUBLE NOT NULL,
    unit                VARCHAR NOT NULL,
    quality             VARCHAR NOT NULL,
    order_id            VARCHAR,
    PRIMARY KEY (reading_id)
);

CREATE TABLE IF NOT EXISTS silver_cycle_events (
    event_id                VARCHAR NOT NULL,
    order_id                VARCHAR NOT NULL,
    event_type              VARCHAR NOT NULL,
    event_time              TIMESTAMP NOT NULL,
    operator_id             VARCHAR,
    quality_check_passed    BOOLEAN,
    sap_confirmation_number VARCHAR,
    goods_movement_document VARCHAR,
    PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS silver_production_orders (
    order_id                VARCHAR NOT NULL,
    material_id             VARCHAR NOT NULL,
    plant                   VARCHAR NOT NULL,
    oven_id                 VARCHAR,
    planned_start           TIMESTAMP,
    planned_end             TIMESTAMP,
    standard_cycle_minutes  INT,
    status                  VARCHAR,
    last_updated            TIMESTAMP,
    PRIMARY KEY (order_id)
);

CREATE TABLE IF NOT EXISTS silver_material_master (
    material_id             VARCHAR NOT NULL,
    material_description    VARCHAR,
    insulation_class        VARCHAR,
    target_moisture_ppm     DOUBLE,
    standard_cycle_minutes  INT,
    max_cycle_minutes       INT,
    target_temperature_degC DOUBLE,
    target_vacuum_mbar      DOUBLE,
    weight_kg               DOUBLE,
    max_temperature_degC    DOUBLE,
    min_vacuum_mbar         DOUBLE,
    last_updated            TIMESTAMP,
    PRIMARY KEY (material_id)
);

-- -----------------------------------------------------------
-- GOLD LAYER -- analytical, joined, aggregated (C12)
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS gold_cycle_summary (
    order_id                    VARCHAR NOT NULL,
    material_id                 VARCHAR NOT NULL,
    material_description        VARCHAR,
    plant                       VARCHAR NOT NULL,
    oven_id                     VARCHAR NOT NULL,
    cycle_start_time            TIMESTAMP,
    cycle_end_time              TIMESTAMP,
    actual_duration_minutes     FLOAT,
    standard_cycle_minutes      INT,
    delta_minutes               FLOAT,
    peak_temperature_degC       DOUBLE,
    min_vacuum_mbar             DOUBLE,
    final_moisture_ppm          DOUBLE,
    target_moisture_ppm         DOUBLE,
    spec_met                    BOOLEAN,
    quality_check_passed        BOOLEAN,
    operator_id                 VARCHAR,
    sap_confirmation_number     VARCHAR,
    goods_movement_posted       BOOLEAN DEFAULT FALSE,
    avg_moisture_ppm            DOUBLE,
    max_temperature_limit_degC  DOUBLE,
    temperature_limit_met       BOOLEAN,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id)
);

-- -----------------------------------------------------------
-- ANALYTICAL VIEWS
-- -----------------------------------------------------------

CREATE OR REPLACE VIEW v_cycle_efficiency AS
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

CREATE OR REPLACE VIEW v_recent_cycles AS
SELECT *
FROM gold_cycle_summary
ORDER BY cycle_start_time DESC
LIMIT 50
