from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from .snowflake_client import _svc
from .transforms.gold import run_gold
from .transforms.silver import run_silver

log = logging.getLogger(__name__)

_INSERT_ORDERS = """
INSERT INTO bronze_sap_production_orders (
    order_id, material_id, plant, oven_id,
    planned_start, planned_end, standard_cycle_minutes, status, raw_payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_MATERIALS = """
INSERT INTO bronze_sap_material_master (
    material_id, material_description, insulation_class, target_moisture_ppm,
    standard_cycle_minutes, max_cycle_minutes, target_temperature_degC,
    target_vacuum_mbar, weight_kg, raw_payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_MES_EVENTS = """
INSERT INTO bronze_mes_events (
    event_id, event_type, raw_payload, order_id, oven_id, operator_id, event_time, payload_json
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_SENSOR_READINGS = """
INSERT INTO bronze_sensor_readings (
    mqtt_topic, raw_payload, reading_id, timestamp_opc, timestamp_mqtt,
    plant_id, oven_id, sensor_type, value, unit, quality, order_id
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def load_if_empty(seed_data_dir: str, sql_dir: str) -> bool:
    row = _svc().fetchone("SELECT COUNT(*) AS row_count FROM gold_cycle_summary")
    current = row.get("row_count", 0) if row else 0
    if current > 0:
        log.info("Seed data already present -- skipping", extra={"gold_rows": current})
        return False

    log.info("Gold layer empty -- loading seed data from Bronze pipeline")
    _load_materials(seed_data_dir)
    _load_production_orders(seed_data_dir)
    _load_historical_cycles_via_bronze(seed_data_dir)
    run_silver(sql_dir)
    run_gold(sql_dir)

    after = _svc().fetchone("SELECT COUNT(*) AS row_count FROM gold_cycle_summary")
    gold_rows = after.get("row_count", 0) if after else 0
    log.info("Seed data loaded", extra={"gold_rows": gold_rows})
    return True


def _load_materials(seed_dir: str) -> None:
    path = os.path.join(seed_dir, "material_masters.json")
    with open(path) as f:
        materials = json.load(f)
    rows = [
        (
            m["material_id"],
            m.get("material_description"),
            m.get("insulation_class"),
            m.get("target_moisture_ppm"),
            m.get("standard_cycle_minutes"),
            m.get("max_cycle_minutes"),
            m.get("target_temperature_degC"),
            m.get("target_vacuum_mbar"),
            m.get("weight_kg"),
            json.dumps(m),
        )
        for m in materials
    ]
    _svc().execute_many(_INSERT_MATERIALS, rows)
    log.info("Seed materials loaded", extra={"count": len(rows)})


def _load_production_orders(seed_dir: str) -> None:
    path = os.path.join(seed_dir, "production_orders.json")
    with open(path) as f:
        orders = json.load(f)
    rows = [
        (
            o["order_id"],
            o.get("material_id"),
            o.get("plant"),
            o.get("oven_id"),
            o.get("planned_start"),
            o.get("planned_end"),
            o.get("standard_cycle_minutes"),
            o.get("status"),
            json.dumps(o),
        )
        for o in orders
    ]
    _svc().execute_many(_INSERT_ORDERS, rows)
    log.info("Seed production orders loaded", extra={"count": len(rows)})


def _load_historical_cycles_via_bronze(seed_dir: str) -> None:
    path = os.path.join(seed_dir, "historical_cycles.json")
    with open(path) as f:
        cycles = json.load(f)

    # Synthetic production orders for historical cycles not in production_orders.json
    order_rows: list[tuple] = []
    for cycle in cycles:
        o = {
            "order_id": cycle["order_id"],
            "material_id": cycle.get("material_id"),
            "plant": cycle.get("plant", "regensburg"),
            "oven_id": cycle.get("oven_id", "oven-01"),
            "planned_start": cycle.get("cycle_start_time"),
            "planned_end": cycle.get("cycle_end_time"),
            "standard_cycle_minutes": cycle.get("standard_cycle_minutes"),
            "status": "CONFIRMED",
        }
        order_rows.append((
            o["order_id"], o["material_id"], o["plant"], o["oven_id"],
            o["planned_start"], o["planned_end"], o["standard_cycle_minutes"],
            o["status"], json.dumps(o),
        ))
    _svc().execute_many(_INSERT_ORDERS, order_rows)
    log.info("Seed historical production orders loaded", extra={"count": len(order_rows)})

    event_rows: list[tuple] = []
    reading_rows: list[tuple] = []

    for cycle in cycles:
        order_id = cycle["order_id"]
        oven_id = cycle.get("oven_id", "oven-01")
        plant = cycle.get("plant", "regensburg")
        operator_id = cycle.get("operator_id")
        start_ts = cycle["cycle_start_time"]
        end_ts = cycle["cycle_end_time"]
        sap_conf = cycle.get("sap_confirmation_number")
        gm_posted = cycle.get("goods_movement_posted", False)

        started_payload = json.dumps({"setpoint_temperature_degC": None, "setpoint_vacuum_mbar": None})
        confirmed_payload = json.dumps({
            "sap_confirmation_number": sap_conf,
            "goods_movement_document": f"GR-SEED-{order_id}" if gm_posted else None,
        })

        started_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "cycle_started",
            "order_id": order_id,
            "oven_id": oven_id,
            "operator_id": operator_id,
            "timestamp": start_ts,
        }
        confirmed_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "cycle_confirmed",
            "order_id": order_id,
            "oven_id": oven_id,
            "operator_id": operator_id,
            "timestamp": end_ts,
        }

        event_rows.append((
            started_event["event_id"], "cycle_started", json.dumps(started_event),
            order_id, oven_id, operator_id, start_ts, started_payload,
        ))
        event_rows.append((
            confirmed_event["event_id"], "cycle_confirmed", json.dumps(confirmed_event),
            order_id, oven_id, operator_id, end_ts, confirmed_payload,
        ))

        topic_base = f"factory/{plant}/{oven_id}"
        for sensor_type, value, unit in [
            ("temperature", cycle.get("peak_temperature_degC"), "degC"),
            ("vacuum", cycle.get("min_vacuum_mbar"), "mbar"),
            ("moisture", cycle.get("final_moisture_ppm"), "ppm"),
        ]:
            if value is None:
                continue
            r_id = str(uuid.uuid4())
            reading = {
                "reading_id": r_id,
                "timestamp_opc": end_ts,
                "timestamp_mqtt": end_ts,
                "plant": plant,
                "oven_id": oven_id,
                "sensor_type": sensor_type,
                "value": value,
                "unit": unit,
                "quality": "Good",
                "order_id": order_id,
            }
            reading_rows.append((
                f"{topic_base}/{sensor_type}", json.dumps(reading),
                r_id, end_ts, end_ts, plant, oven_id,
                sensor_type, value, unit, "Good", order_id,
            ))

    _svc().execute_many(_INSERT_MES_EVENTS, event_rows)
    _svc().execute_many(_INSERT_SENSOR_READINGS, reading_rows)
    log.info(
        "Seed historical cycles loaded into Bronze",
        extra={"cycles": len(cycles), "events": len(event_rows), "readings": len(reading_rows)},
    )
