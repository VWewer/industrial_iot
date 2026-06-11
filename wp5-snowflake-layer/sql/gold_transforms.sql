-- Gold transform: Silver -> gold_cycle_summary
-- Only processes cycles with BOTH cycle_started AND cycle_confirmed events.
-- Upserts: matched rows are updated (cycle may have richer sensor data over time).

MERGE INTO gold_cycle_summary AS target
USING (
    SELECT
        ce_start.order_id,
        po.material_id,
        mm.material_description,
        po.plant,
        COALESCE(po.oven_id, '')                                          AS oven_id,
        ce_start.event_time                                               AS cycle_start_time,
        ce_end.event_time                                                 AS cycle_end_time,
        DATEDIFF('minute', ce_start.event_time, ce_end.event_time)::FLOAT AS actual_duration_minutes,
        po.standard_cycle_minutes,
        DATEDIFF('minute', ce_start.event_time, ce_end.event_time)::FLOAT
            - po.standard_cycle_minutes                                   AS delta_minutes,
        sr_peaks.peak_temperature_degC,
        sr_peaks.min_vacuum_mbar,
        sr_final.final_moisture_ppm,
        sr_peaks.avg_moisture_ppm,
        mm.target_moisture_ppm,
        (sr_final.final_moisture_ppm < mm.target_moisture_ppm)           AS spec_met,
        ce_end.quality_check_passed,
        ce_start.operator_id,
        ce_end.sap_confirmation_number,
        (ce_end.goods_movement_document IS NOT NULL)                      AS goods_movement_posted,
        mm.max_temperature_degC                                           AS max_temperature_limit_degC,
        CASE
            WHEN mm.max_temperature_degC IS NOT NULL
            THEN (sr_peaks.peak_temperature_degC <= mm.max_temperature_degC)
            ELSE NULL
        END                                                               AS temperature_limit_met
    FROM (
        SELECT *
        FROM silver_cycle_events
        WHERE event_type = 'cycle_started'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY event_time) = 1
    ) ce_start
    JOIN (
        SELECT *
        FROM silver_cycle_events
        WHERE event_type = 'cycle_confirmed'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY event_time DESC) = 1
    ) ce_end ON ce_start.order_id = ce_end.order_id
    LEFT JOIN silver_production_orders po
        ON po.order_id = ce_start.order_id
    LEFT JOIN silver_material_master mm
        ON mm.material_id = po.material_id
    LEFT JOIN (
        SELECT
            order_id,
            MAX(CASE WHEN sensor_type = 'temperature' THEN value END) AS peak_temperature_degC,
            MIN(CASE WHEN sensor_type = 'vacuum'      THEN value END) AS min_vacuum_mbar,
            AVG(CASE WHEN sensor_type = 'moisture'    THEN value END) AS avg_moisture_ppm
        FROM silver_sensor_readings
        WHERE order_id IS NOT NULL
        GROUP BY order_id
    ) sr_peaks ON sr_peaks.order_id = ce_start.order_id
    LEFT JOIN (
        SELECT order_id, value AS final_moisture_ppm
        FROM (
            SELECT
                order_id,
                value,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY timestamp_opc DESC
                ) AS rn
            FROM silver_sensor_readings
            WHERE sensor_type = 'moisture'
              AND order_id IS NOT NULL
        ) ranked
        WHERE rn = 1
    ) sr_final ON sr_final.order_id = ce_start.order_id
) AS source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET
    material_id                = source.material_id,
    material_description       = source.material_description,
    plant                      = source.plant,
    oven_id                    = source.oven_id,
    cycle_start_time           = source.cycle_start_time,
    cycle_end_time             = source.cycle_end_time,
    actual_duration_minutes    = source.actual_duration_minutes,
    standard_cycle_minutes     = source.standard_cycle_minutes,
    delta_minutes              = source.delta_minutes,
    peak_temperature_degC      = source.peak_temperature_degC,
    min_vacuum_mbar            = source.min_vacuum_mbar,
    final_moisture_ppm         = source.final_moisture_ppm,
    avg_moisture_ppm           = source.avg_moisture_ppm,
    target_moisture_ppm        = source.target_moisture_ppm,
    spec_met                   = source.spec_met,
    quality_check_passed       = source.quality_check_passed,
    operator_id                = source.operator_id,
    sap_confirmation_number    = source.sap_confirmation_number,
    goods_movement_posted      = source.goods_movement_posted,
    max_temperature_limit_degC = source.max_temperature_limit_degC,
    temperature_limit_met      = source.temperature_limit_met
WHEN NOT MATCHED THEN INSERT (
    order_id, material_id, material_description, plant, oven_id,
    cycle_start_time, cycle_end_time, actual_duration_minutes,
    standard_cycle_minutes, delta_minutes,
    peak_temperature_degC, min_vacuum_mbar, final_moisture_ppm, avg_moisture_ppm,
    target_moisture_ppm, spec_met, quality_check_passed,
    operator_id, sap_confirmation_number, goods_movement_posted,
    max_temperature_limit_degC, temperature_limit_met
) VALUES (
    source.order_id, source.material_id, source.material_description, source.plant, source.oven_id,
    source.cycle_start_time, source.cycle_end_time, source.actual_duration_minutes,
    source.standard_cycle_minutes, source.delta_minutes,
    source.peak_temperature_degC, source.min_vacuum_mbar, source.final_moisture_ppm, source.avg_moisture_ppm,
    source.target_moisture_ppm, source.spec_met, source.quality_check_passed,
    source.operator_id, source.sap_confirmation_number, source.goods_movement_posted,
    source.max_temperature_limit_degC, source.temperature_limit_met
)
