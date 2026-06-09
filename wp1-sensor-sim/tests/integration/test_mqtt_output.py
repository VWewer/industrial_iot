"""Integration test: validates published MQTT payloads against the C1 contract schema.

Requires a running MQTT broker. Excluded from default pytest run.
Run explicitly: pytest tests/integration/ --integration
"""
from __future__ import annotations

import json
import time
from typing import Any

import pytest

# Skip unless --integration flag is passed
pytestmark = pytest.mark.integration

C1_REQUIRED_FIELDS = {
    "reading_id", "timestamp_opc", "timestamp_mqtt",
    "plant", "oven_id", "sensor_type", "value", "unit",
    "quality", "order_id",
}
VALID_SENSOR_TYPES = {"temperature", "vacuum", "moisture"}
VALID_UNITS = {"degC", "mbar", "ppm"}
VALID_QUALITY = {"Good", "Bad", "Uncertain"}


def validate_c1_payload(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors; empty list = valid."""
    errors: list[str] = []

    for field in C1_REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    if "sensor_type" in payload and payload["sensor_type"] not in VALID_SENSOR_TYPES:
        errors.append(f"Invalid sensor_type: {payload['sensor_type']}")

    if "unit" in payload and payload["unit"] not in VALID_UNITS:
        errors.append(f"Invalid unit: {payload['unit']}")

    if "quality" in payload and payload["quality"] not in VALID_QUALITY:
        errors.append(f"Invalid quality: {payload['quality']}")

    if "value" in payload and not isinstance(payload["value"], (int, float)):
        errors.append(f"value must be numeric, got {type(payload['value'])}")

    if "timestamp_opc" in payload:
        ts = payload["timestamp_opc"]
        if not (isinstance(ts, str) and ts.endswith("Z") and "T" in ts):
            errors.append(f"timestamp_opc not ISO 8601 UTC: {ts}")

    if "timestamp_mqtt" in payload:
        ts = payload["timestamp_mqtt"]
        if not (isinstance(ts, str) and ts.endswith("Z") and "T" in ts):
            errors.append(f"timestamp_mqtt not ISO 8601 UTC: {ts}")

    return errors


def test_c1_payload_validation_logic():
    """Self-test: ensure validator catches known bad payloads."""
    good = {
        "reading_id": "abc-123",
        "timestamp_opc": "2026-06-03T10:00:00.000Z",
        "timestamp_mqtt": "2026-06-03T10:00:00.001Z",
        "plant": "regensburg",
        "oven_id": "oven-01",
        "sensor_type": "temperature",
        "value": 120.5,
        "unit": "degC",
        "quality": "Good",
        "order_id": "ORD-2026-00042",
    }
    assert validate_c1_payload(good) == []

    bad_type = dict(good, sensor_type="heater-power")
    assert len(validate_c1_payload(bad_type)) > 0

    missing_field = {k: v for k, v in good.items() if k != "reading_id"}
    assert len(validate_c1_payload(missing_field)) > 0
