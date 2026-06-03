"""
contracts/validators/validate_c1_mqtt.py

Validates a MQTT sensor reading payload (Contract C1) against the schema
defined in DOMAIN-MODEL.md Section 1.3.

Usage:
    python validate_c1_mqtt.py '{"reading_id": "...", ...}'
    python validate_c1_mqtt.py --file sample_reading.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import sys
import re
from datetime import datetime
from typing import Any


VALID_SENSOR_TYPES = {"temperature", "vacuum", "moisture"}
VALID_UNITS = {"degC", "mbar", "ppm"}
VALID_QUALITY = {"Good", "Bad", "Uncertain"}
VALID_PLANTS = {"regensburg", "kirchheim"}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
OVEN_RE = re.compile(r"^oven-\d{2}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def validate(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    # reading_id — UUID v4
    rid = payload.get("reading_id")
    if not isinstance(rid, str) or not UUID_RE.match(rid):
        errors.append(f"reading_id: must be UUID v4 string, got {rid!r}")

    # order_id — string or null
    oid = payload.get("order_id")
    if oid is not None and not isinstance(oid, str):
        errors.append(f"order_id: must be string or null, got {type(oid).__name__}")

    # oven_id — format oven-NN
    oven = payload.get("oven_id")
    if not isinstance(oven, str) or not OVEN_RE.match(oven):
        errors.append(f"oven_id: must match 'oven-NN' format, got {oven!r}")

    # plant — enum
    plant = payload.get("plant")
    if plant not in VALID_PLANTS:
        errors.append(f"plant: must be one of {VALID_PLANTS}, got {plant!r}")

    # sensor_type — enum
    stype = payload.get("sensor_type")
    if stype not in VALID_SENSOR_TYPES:
        errors.append(f"sensor_type: must be one of {VALID_SENSOR_TYPES}, got {stype!r}")

    # value — float or int
    value = payload.get("value")
    if not isinstance(value, (int, float)):
        errors.append(f"value: must be numeric, got {type(value).__name__}")

    # unit — enum, must be consistent with sensor_type
    unit = payload.get("unit")
    if unit not in VALID_UNITS:
        errors.append(f"unit: must be one of {VALID_UNITS}, got {unit!r}")
    else:
        expected = {"temperature": "degC", "vacuum": "mbar", "moisture": "ppm"}
        if stype in expected and unit != expected[stype]:
            errors.append(
                f"unit/sensor_type mismatch: sensor_type={stype!r} requires unit={expected[stype]!r}, got {unit!r}"
            )

    # quality — enum
    quality = payload.get("quality")
    if quality not in VALID_QUALITY:
        errors.append(f"quality: must be one of {VALID_QUALITY}, got {quality!r}")

    # timestamp_opc — ISO 8601 UTC
    ts_opc = payload.get("timestamp_opc")
    if not isinstance(ts_opc, str) or not ISO_RE.match(ts_opc):
        errors.append(f"timestamp_opc: must be ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ), got {ts_opc!r}")

    # timestamp_mqtt — ISO 8601 UTC
    ts_mqtt = payload.get("timestamp_mqtt")
    if not isinstance(ts_mqtt, str) or not ISO_RE.match(ts_mqtt):
        errors.append(f"timestamp_mqtt: must be ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ), got {ts_mqtt!r}")

    # No extra fields (warn only)
    known = {
        "reading_id", "order_id", "oven_id", "plant",
        "sensor_type", "value", "unit", "quality",
        "timestamp_opc", "timestamp_mqtt",
    }
    extra = set(payload.keys()) - known
    if extra:
        errors.append(f"WARNING — unexpected fields (not in contract): {extra}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c1_mqtt.py '<json_string>'")
        print("       python validate_c1_mqtt.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("✓ VALID — payload matches Contract C1 (MQTT sensor reading)")
        sys.exit(0)
    else:
        print(f"✗ INVALID — {len(errors)} error(s) found:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
