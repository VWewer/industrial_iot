"""Integration test: WP1 MQTT stream -> WP2 historian -> /process-state.

Requires a live Mosquitto broker on localhost:1883 and WP1 running.
Deselect with: pytest -m "not integration"
"""
from __future__ import annotations

import json
import time
import uuid

import pytest

try:
    import paho.mqtt.client as mqtt
    from fastapi.testclient import TestClient

    from src.api import app, init_app
    from src.historian import Historian
    from src.subscriber import SensorSubscriber
except ImportError:
    pytest.skip("paho-mqtt not installed", allow_module_level=True)

BROKER_HOST = "localhost"
BROKER_PORT = 1883
OVEN_ID = "oven-01"
PLANT_ID = "regensburg"
ORDER_ID = "ORD-2026-INT-001"


def _publish_reading(
    pub_client: mqtt.Client,
    sensor_type: str,
    value: float,
    order_id: str | None = ORDER_ID,
) -> None:
    ts = "2026-06-01T08:00:00.000Z"
    payload = {
        "reading_id": str(uuid.uuid4()),
        "timestamp_opc": ts,
        "timestamp_mqtt": ts,
        "plant": PLANT_ID,
        "oven_id": OVEN_ID,
        "sensor_type": sensor_type,
        "value": value,
        "unit": "degC",
        "quality": "Good",
        "order_id": order_id,
    }
    topic = f"factory/{PLANT_ID}/{OVEN_ID}/{sensor_type}"
    pub_client.publish(topic, json.dumps(payload), qos=1)


@pytest.fixture(scope="module")
def mqtt_publisher():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wp2-integration-test-pub")
    try:
        client.connect(BROKER_HOST, BROKER_PORT)
        client.loop_start()
    except OSError:
        pytest.skip("MQTT broker not available")
    yield client
    client.loop_stop()
    client.disconnect()


@pytest.fixture(scope="module")
def subscriber_and_client():
    h = Historian(max_readings=100)
    init_app(h, moisture_threshold=500.0, max_cycle_minutes=600.0)
    sub = SensorSubscriber(historian=h, broker_host=BROKER_HOST, broker_port=BROKER_PORT)
    try:
        sub.connect()
    except Exception:
        pytest.skip("MQTT broker not available")
    time.sleep(0.5)  # allow connection to establish
    yield TestClient(app), h
    sub.disconnect()


@pytest.mark.integration
def test_published_reading_appears_in_process_state(mqtt_publisher, subscriber_and_client):
    client, h = subscriber_and_client
    _publish_reading(mqtt_publisher, "temperature", 115.0)
    _publish_reading(mqtt_publisher, "moisture", 1800.0)
    time.sleep(2.0)  # allow MQTT message to round-trip

    resp = client.get(f"/process-state/{OVEN_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["temperature_degC"] is not None
    assert abs(body["temperature_degC"] - 115.0) < 0.1


@pytest.mark.integration
def test_moisture_below_threshold_triggers_cycle_complete(mqtt_publisher, subscriber_and_client):
    client, h = subscriber_and_client
    _publish_reading(mqtt_publisher, "moisture", 200.0)  # below 500 threshold
    time.sleep(2.0)

    resp = client.get(f"/process-state/{OVEN_ID}")
    assert resp.json()["status"] == "cycle_complete"


@pytest.mark.integration
def test_historian_query_returns_published_readings(mqtt_publisher, subscriber_and_client):
    client, h = subscriber_and_client
    time.sleep(1.0)

    resp = client.get(f"/historian?order_id={ORDER_ID}&sensor_type=temperature")
    body = resp.json()
    assert body["count"] >= 1
    assert all(r["sensor_type"] == "temperature" for r in body["readings"])
