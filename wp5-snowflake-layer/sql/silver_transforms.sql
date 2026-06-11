-- Silver transforms: Bronze -> Silver
-- Deduplication uses QUALIFY ROW_NUMBER() (Snowflake-native).
-- Only inserts rows WHEN NOT MATCHED -- existing Silver rows are never overwritten
-- except for production orders and material master which MERGE UPDATE on newer data.

-- 1. silver_sensor_readings: Good-quality readings only, deduplicated on reading_id
MERGE INTO silver_sensor_readings AS target
USING (
    SELECT reading_id, timestamp_opc, plant_id, oven_id, sensor_type, value, unit, quality, order_id
    FROM bronze_sensor_readings
    WHERE quality = 'Good'
      AND reading_id IS NOT NULL
      AND timestamp_opc IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY reading_id ORDER BY ingested_at) = 1
) AS source
ON target.reading_id = source.reading_id
WHEN NOT MATCHED THEN INSERT (
    reading_id, timestamp_opc, plant_id, oven_id, sensor_type, value, unit, quality, order_id
) VALUES (
    source.reading_id, source.timestamp_opc, source.plant_id, source.oven_id,
    source.sensor_type, source.value, source.unit, source.quality, source.order_id
);

-- 2. silver_cycle_events: deduplicated on event_id, payload_json parsed for cycle_confirmed fields
MERGE INTO silver_cycle_events AS target
USING (
    SELECT
        event_id,
        order_id,
        event_type,
        event_time,
        operator_id,
        TRY_PARSE_JSON(payload_json):quality_check_passed::BOOLEAN   AS quality_check_passed,
        TRY_PARSE_JSON(payload_json):sap_confirmation_number::VARCHAR AS sap_confirmation_number,
        TRY_PARSE_JSON(payload_json):goods_movement_document::VARCHAR AS goods_movement_document
    FROM bronze_mes_events
    WHERE event_id IS NOT NULL
      AND order_id IS NOT NULL
      AND event_time IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at) = 1
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN INSERT (
    event_id, order_id, event_type, event_time, operator_id,
    quality_check_passed, sap_confirmation_number, goods_movement_document
) VALUES (
    source.event_id, source.order_id, source.event_type, source.event_time, source.operator_id,
    source.quality_check_passed, source.sap_confirmation_number, source.goods_movement_document
);

-- 3. silver_production_orders: latest version per order_id (upsert on ingested_at DESC)
MERGE INTO silver_production_orders AS target
USING (
    SELECT
        order_id, material_id, plant, oven_id,
        planned_start, planned_end, standard_cycle_minutes, status,
        ingested_at AS last_updated
    FROM bronze_sap_production_orders
    WHERE order_id IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY ingested_at DESC) = 1
) AS source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET
    material_id            = source.material_id,
    plant                  = source.plant,
    oven_id                = source.oven_id,
    planned_start          = source.planned_start,
    planned_end            = source.planned_end,
    standard_cycle_minutes = source.standard_cycle_minutes,
    status                 = source.status,
    last_updated           = source.last_updated
WHEN NOT MATCHED THEN INSERT (
    order_id, material_id, plant, oven_id,
    planned_start, planned_end, standard_cycle_minutes, status, last_updated
) VALUES (
    source.order_id, source.material_id, source.plant, source.oven_id,
    source.planned_start, source.planned_end, source.standard_cycle_minutes,
    source.status, source.last_updated
);

-- 4. silver_material_master: latest version per material_id
MERGE INTO silver_material_master AS target
USING (
    SELECT
        material_id, material_description, insulation_class, target_moisture_ppm,
        standard_cycle_minutes, max_cycle_minutes, target_temperature_degC,
        target_vacuum_mbar, weight_kg, max_temperature_degC, min_vacuum_mbar,
        ingested_at AS last_updated
    FROM bronze_sap_material_master
    WHERE material_id IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY material_id ORDER BY ingested_at DESC) = 1
) AS source
ON target.material_id = source.material_id
WHEN MATCHED THEN UPDATE SET
    material_description    = source.material_description,
    insulation_class        = source.insulation_class,
    target_moisture_ppm     = source.target_moisture_ppm,
    standard_cycle_minutes  = source.standard_cycle_minutes,
    max_cycle_minutes       = source.max_cycle_minutes,
    target_temperature_degC = source.target_temperature_degC,
    target_vacuum_mbar      = source.target_vacuum_mbar,
    weight_kg               = source.weight_kg,
    max_temperature_degC    = source.max_temperature_degC,
    min_vacuum_mbar         = source.min_vacuum_mbar,
    last_updated            = source.last_updated
WHEN NOT MATCHED THEN INSERT (
    material_id, material_description, insulation_class, target_moisture_ppm,
    standard_cycle_minutes, max_cycle_minutes, target_temperature_degC,
    target_vacuum_mbar, weight_kg, max_temperature_degC, min_vacuum_mbar, last_updated
) VALUES (
    source.material_id, source.material_description, source.insulation_class,
    source.target_moisture_ppm, source.standard_cycle_minutes, source.max_cycle_minutes,
    source.target_temperature_degC, source.target_vacuum_mbar, source.weight_kg,
    source.max_temperature_degC, source.min_vacuum_mbar, source.last_updated
)
