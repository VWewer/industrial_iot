from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.models import CycleEvent, SensorReading


class TestSensorReadingModel:
    def test_valid_reading(self):
        r = SensorReading(
            reading_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            timestamp_opc="2026-06-03T08:32:14.521Z",
            timestamp_mqtt="2026-06-03T08:32:14.523Z",
            plant="regensburg",
            oven_id="oven-01",
            sensor_type="temperature",
            value=142.3,
            unit="degC",
            quality="Good",
            order_id="ORD-2026-00042",
        )
        assert r.sensor_type == "temperature"
        assert r.quality == "Good"

    def test_invalid_sensor_type(self):
        with pytest.raises(ValidationError):
            SensorReading(
                reading_id="id",
                timestamp_opc="2026-06-03T08:00:00Z",
                timestamp_mqtt="2026-06-03T08:00:00Z",
                plant="regensburg",
                oven_id="oven-01",
                sensor_type="pressure",  # invalid
                value=1.0,
                unit="bar",
                quality="Good",
            )

    def test_invalid_quality(self):
        with pytest.raises(ValidationError):
            SensorReading(
                reading_id="id",
                timestamp_opc="2026-06-03T08:00:00Z",
                timestamp_mqtt="2026-06-03T08:00:00Z",
                plant="regensburg",
                oven_id="oven-01",
                sensor_type="temperature",
                value=100.0,
                unit="degC",
                quality="Unknown",  # invalid
            )

    def test_timestamp_without_ms(self):
        r = SensorReading(
            reading_id="id",
            timestamp_opc="2026-06-03T08:00:00Z",  # no milliseconds -- still valid
            timestamp_mqtt="2026-06-03T08:00:00Z",
            plant="regensburg",
            oven_id="oven-01",
            sensor_type="vacuum",
            value=5.1,
            unit="mbar",
            quality="Good",
        )
        assert r.timestamp_opc == "2026-06-03T08:00:00Z"

    def test_timestamp_missing_z_suffix(self):
        with pytest.raises(ValidationError):
            SensorReading(
                reading_id="id",
                timestamp_opc="2026-06-03T08:00:00",  # missing Z
                timestamp_mqtt="2026-06-03T08:00:00Z",
                plant="regensburg",
                oven_id="oven-01",
                sensor_type="temperature",
                value=100.0,
                unit="degC",
                quality="Good",
            )

    def test_order_id_optional(self):
        r = SensorReading(
            reading_id="id",
            timestamp_opc="2026-06-03T08:00:00Z",
            timestamp_mqtt="2026-06-03T08:00:00Z",
            plant="regensburg",
            oven_id="oven-01",
            sensor_type="moisture",
            value=350.0,
            unit="ppm",
            quality="Uncertain",
            order_id=None,
        )
        assert r.order_id is None


class TestCycleEventModel:
    def test_valid_cycle_started(self):
        e = CycleEvent(
            event_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
            event_type="cycle_started",
            order_id="ORD-2026-00042",
            oven_id="oven-01",
            operator_id="OP-007",
            timestamp="2026-06-03T06:05:00Z",
            payload={"setpoint_temperature_degC": 130.0},
        )
        assert e.event_type == "cycle_started"

    def test_valid_cycle_confirmed(self):
        e = CycleEvent(
            event_id="abc123",
            event_type="cycle_confirmed",
            order_id="ORD-2026-00042",
            oven_id="oven-01",
            timestamp="2026-06-03T14:00:00Z",
            payload={"sap_confirmation_number": "CONF-001", "goods_movement_document": "GR-001"},
        )
        assert e.payload["sap_confirmation_number"] == "CONF-001"

    def test_invalid_event_type(self):
        with pytest.raises(ValidationError):
            CycleEvent(
                event_id="id",
                event_type="unknown_type",
                order_id="ORD-2026-00042",
                oven_id="oven-01",
                timestamp="2026-06-03T06:00:00Z",
            )

    def test_payload_optional(self):
        e = CycleEvent(
            event_id="id",
            event_type="cycle_aborted",
            order_id="ORD-2026-00042",
            oven_id="oven-01",
            timestamp="2026-06-03T07:00:00Z",
            payload=None,
        )
        assert e.payload is None


class TestMQTTSubscriberInsert:
    def test_insert_called_on_valid_message(self, mock_sf):
        from src.ingestion.mqtt_subscriber import MQTTSubscriber

        sub = MQTTSubscriber("localhost", 1883)
        payload = json.dumps({
            "reading_id": "test-id-001",
            "timestamp_opc": "2026-06-03T08:00:00Z",
            "timestamp_mqtt": "2026-06-03T08:00:00Z",
            "plant": "regensburg",
            "oven_id": "oven-01",
            "sensor_type": "temperature",
            "value": 120.5,
            "unit": "degC",
            "quality": "Good",
            "order_id": "ORD-2026-00042",
        })

        msg = MagicMock()
        msg.topic = "factory/regensburg/oven-01/temperature"
        msg.payload = payload.encode()

        sub._on_message(None, None, msg)

        mock_sf.execute_many.assert_called_once()
        args = mock_sf.execute_many.call_args[0]
        row = args[1][0]
        assert row[2] == "test-id-001"  # reading_id
        assert row[7] == "temperature"  # sensor_type

    def test_malformed_json_is_dropped(self, mock_sf):
        from src.ingestion.mqtt_subscriber import MQTTSubscriber

        sub = MQTTSubscriber("localhost", 1883)
        msg = MagicMock()
        msg.topic = "factory/regensburg/oven-01/temperature"
        msg.payload = b"not json"

        sub._on_message(None, None, msg)

        mock_sf.execute_many.assert_not_called()

    def test_invalid_sensor_type_is_dropped(self, mock_sf):
        from src.ingestion.mqtt_subscriber import MQTTSubscriber

        sub = MQTTSubscriber("localhost", 1883)
        payload = json.dumps({
            "reading_id": "id",
            "timestamp_opc": "2026-06-03T08:00:00Z",
            "timestamp_mqtt": "2026-06-03T08:00:00Z",
            "plant": "regensburg",
            "oven_id": "oven-01",
            "sensor_type": "pressure",  # invalid
            "value": 1.0,
            "unit": "bar",
            "quality": "Good",
        })
        msg = MagicMock()
        msg.topic = "factory/regensburg/oven-01/pressure"
        msg.payload = payload.encode()

        sub._on_message(None, None, msg)

        mock_sf.execute_many.assert_not_called()
