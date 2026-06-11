"""
End-to-end integration test: simulate one drying cycle through WP5.

Requirements (all must be running):
  - Mosquitto MQTT broker on localhost:1883
  - WP4 SAP mock on localhost:8003
  - Snowflake account (credentials in wp5-snowflake-layer/.env)

Skip automatically when Snowflake or MQTT are not available.
Run with: pytest tests/integration/ -m integration -v
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest

pytestmark = pytest.mark.integration


def _snowflake_available() -> bool:
    try:
        from dotenv import load_dotenv
        load_dotenv(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        )
        import snowflake.connector
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT", ""),
            user=os.getenv("SNOWFLAKE_USER", ""),
            password=os.getenv("SNOWFLAKE_PASSWORD", ""),
            database=os.getenv("SNOWFLAKE_DATABASE", "INDUSTRIAL_IOT_DEMO"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        )
        conn.close()
        return True
    except Exception:
        return False


def _mqtt_available() -> bool:
    try:
        import paho.mqtt.client as mqtt
        c = mqtt.Client()
        c.connect("localhost", 1883, keepalive=5)
        c.disconnect()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def require_services():
    if not _snowflake_available():
        pytest.skip("Snowflake not available")
    if not _mqtt_available():
        pytest.skip("MQTT broker not available")


def _make_sf_client():
    from src.snowflake_client import SnowflakeClient
    client = SnowflakeClient(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
    )
    client.connect()
    return client


class TestEndToEnd:
    def test_bronze_to_gold_via_direct_insert(self):
        """Insert Bronze records directly and run transforms -- verify Gold row appears."""
        import src.snowflake_client as sf_module
        sf_module._client = _make_sf_client()
        client = sf_module._client

        sql_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "sql")
        )

        order_id = f"ORD-TEST-{uuid.uuid4().hex[:8].upper()}"
        start_ts = "2026-06-11T06:00:00Z"
        end_ts = "2026-06-11T14:00:00Z"

        # Insert Bronze MES events
        started_id = str(uuid.uuid4())
        confirmed_id = str(uuid.uuid4())
        client.execute_many(
            """INSERT INTO bronze_mes_events (event_id, event_type, raw_payload, order_id, oven_id, event_time, payload_json)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (started_id, "cycle_started", "{}", order_id, "oven-01", start_ts, None),
                (confirmed_id, "cycle_confirmed", "{}", order_id, "oven-01", end_ts,
                 json.dumps({"sap_confirmation_number": "CONF-E2E-001", "goods_movement_document": None})),
            ],
        )

        # Insert Bronze SAP production order
        client.execute_many(
            """INSERT INTO bronze_sap_production_orders (order_id, material_id, plant, oven_id, standard_cycle_minutes, status, raw_payload)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [(order_id, "MAT-0001", "regensburg", "oven-01", 480, "CONFIRMED", "{}")],
        )

        # Insert Bronze material master (needed for spec_met and target_moisture_ppm in Gold)
        client.execute_many(
            """INSERT INTO bronze_sap_material_master (material_id, material_description, target_moisture_ppm, standard_cycle_minutes, raw_payload)
               VALUES (%s, %s, %s, %s, %s)""",
            [("MAT-0001", "Power Transformer 100MVA", 300.0, 480, "{}")],
        )

        # Insert Bronze sensor readings
        for sensor_type, value, unit in [
            ("temperature", 129.0, "degC"),
            ("vacuum", 5.0, "mbar"),
            ("moisture", 285.0, "ppm"),
        ]:
            r_id = str(uuid.uuid4())
            client.execute_many(
                """INSERT INTO bronze_sensor_readings (mqtt_topic, raw_payload, reading_id, timestamp_opc, timestamp_mqtt, plant_id, oven_id, sensor_type, value, unit, quality, order_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [("factory/regensburg/oven-01/" + sensor_type, "{}", r_id, end_ts, end_ts,
                  "regensburg", "oven-01", sensor_type, value, unit, "Good", order_id)],
            )

        # Run Silver transforms
        from src.transforms.silver import run_silver
        run_silver(sql_dir)

        # Run Gold transforms
        from src.transforms.gold import run_gold
        run_gold(sql_dir)

        # Verify Gold row
        row = client.fetchone(
            "SELECT * FROM gold_cycle_summary WHERE order_id = %s", (order_id,)
        )
        assert row is not None, f"Gold row not found for {order_id}"
        assert row["order_id"] == order_id
        assert row["material_id"] == "MAT-0001"
        assert row["spec_met"] is True  # 285 < 300

        # Cleanup
        client.execute(f"DELETE FROM gold_cycle_summary WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM silver_cycle_events WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM silver_sensor_readings WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM silver_production_orders WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM bronze_mes_events WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM bronze_sap_production_orders WHERE order_id = '{order_id}'")
        client.execute(f"DELETE FROM bronze_sap_material_master WHERE material_id = 'MAT-0001' AND raw_payload = '{{}}'")
        client.execute(f"DELETE FROM bronze_sensor_readings WHERE order_id = '{order_id}'")
        client.close()
        sf_module._client = None
