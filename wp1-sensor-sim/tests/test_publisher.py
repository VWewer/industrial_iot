"""Unit tests for the MQTT publisher."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import MQTTConnectionError
from src.models import SensorType
from src.publisher import SensorPublisher, TOPIC_TEMPLATE, _utc_now


class TestSensorPublisher:
    def _make_publisher(self) -> SensorPublisher:
        return SensorPublisher(
            broker_host="localhost",
            broker_port=1883,
            plant="regensburg",
            oven_id="oven-01",
        )

    def test_connect_raises_on_os_error(self):
        pub = self._make_publisher()
        with patch.object(pub._client, "connect", side_effect=OSError("refused")):
            with pytest.raises(MQTTConnectionError):
                pub.connect()

    def test_publish_readings_sends_one_message_per_sensor(self):
        pub = self._make_publisher()
        pub._client = MagicMock()
        pub._client.publish.return_value = MagicMock(rc=0)

        values = {
            SensorType.TEMPERATURE: 115.2,
            SensorType.VACUUM: 4.8,
            SensorType.MOISTURE: 850.0,
        }
        pub.publish_readings(values, order_id="ORD-2026-00042")

        assert pub._client.publish.call_count == 3

    def test_publish_uses_correct_topics(self):
        pub = self._make_publisher()
        pub._client = MagicMock()
        pub._client.publish.return_value = MagicMock(rc=0)

        values = {SensorType.TEMPERATURE: 100.0}
        pub.publish_readings(values, order_id=None)

        call_args = pub._client.publish.call_args
        topic = call_args[0][0]
        assert topic == "factory/regensburg/oven-01/temperature"

    def test_published_payload_is_valid_json(self):
        pub = self._make_publisher()
        captured = []
        pub._client = MagicMock()
        pub._client.publish.side_effect = lambda topic, payload, qos: (
            captured.append(json.loads(payload)) or MagicMock(rc=0)
        )

        values = {SensorType.VACUUM: 5.1}
        pub.publish_readings(values, order_id="ORD-2026-00042")

        assert len(captured) == 1
        msg = captured[0]
        assert msg["sensor_type"] == "vacuum"
        assert msg["unit"] == "mbar"
        assert msg["plant"] == "regensburg"
        assert msg["oven_id"] == "oven-01"
        assert msg["order_id"] == "ORD-2026-00042"

    def test_publish_with_null_order_id(self):
        pub = self._make_publisher()
        captured = []
        pub._client = MagicMock()
        pub._client.publish.side_effect = lambda topic, payload, qos: (
            captured.append(json.loads(payload)) or MagicMock(rc=0)
        )

        pub.publish_readings({SensorType.MOISTURE: 1200.0}, order_id=None)

        assert captured[0]["order_id"] is None

    def test_payload_contains_required_c1_fields(self):
        pub = self._make_publisher()
        captured = []
        pub._client = MagicMock()
        pub._client.publish.side_effect = lambda topic, payload, qos: (
            captured.append(json.loads(payload)) or MagicMock(rc=0)
        )

        pub.publish_readings({SensorType.TEMPERATURE: 120.0}, order_id="ORD-2026-00042")
        msg = captured[0]

        required = {
            "reading_id", "timestamp_opc", "timestamp_mqtt",
            "plant", "oven_id", "sensor_type", "value", "unit",
            "quality", "order_id",
        }
        assert required.issubset(msg.keys())

    def test_publish_uses_qos_1(self):
        pub = self._make_publisher()
        pub._client = MagicMock()
        pub._client.publish.return_value = MagicMock(rc=0)

        pub.publish_readings({SensorType.TEMPERATURE: 100.0}, order_id=None)

        _, kwargs = pub._client.publish.call_args
        assert kwargs.get("qos") == 1 or pub._client.publish.call_args[0][2] == 1


class TestUtcNow:
    def test_utc_now_ends_with_z(self):
        ts = _utc_now()
        assert ts.endswith("Z")

    def test_utc_now_is_iso_format(self):
        ts = _utc_now()
        # Quick structural check: YYYY-MM-DDTHH:MM:SS.mmmZ
        assert len(ts) == 24
        assert ts[10] == "T"
