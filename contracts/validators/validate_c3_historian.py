"""
contracts/validators/validate_c3_historian.py

Validates a HistorianResponse payload (Contract C3) against the schema
defined in contracts/interface-contracts.md C3.

Usage:
    python validate_c3_historian.py '<json_string>'
    python validate_c3_historian.py --file sample.json

Exit code 0 = valid, 1 = invalid.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

VALID_SENSOR_TYPES = {"temperature", "vacuum", "moisture"}
VALID_UNITS = {"degC", "mbar", "ppm"}
VALID_QUALITY = {"Good", "Bad", "Uncertain"}
ORDER_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _validate_reading(reading: Any, idx: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(reading, dict):
        return [f"readings[{idx}]: must be object, got {type(reading).__name__}"]

    rid = reading.get("reading_id")
    if not isinstance(rid, str) or not UUID_RE.match(rid):
        errors.append(f"readings[{idx}].reading_id: must be UUID v4, got {rid!r}")

    ts = reading.get("timestamp_opc")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"readings[{idx}].timestamp_opc: must be ISO 8601 UTC, got {ts!r}")

    stype = reading.get("sensor_type")
    if stype not in VALID_SENSOR_TYPES:
        errors.append(f"readings[{idx}].sensor_type: must be one of {sorted(VALID_SENSOR_TYPES)}, got {stype!r}")

    val = reading.get("value")
    if not isinstance(val, (int, float)):
        errors.append(f"readings[{idx}].value: must be float, got {type(val).__name__}")

    unit = reading.get("unit")
    if unit not in VALID_UNITS:
        errors.append(f"readings[{idx}].unit: must be one of {sorted(VALID_UNITS)}, got {unit!r}")

    quality = reading.get("quality")
    if quality not in VALID_QUALITY:
        errors.append(f"readings[{idx}].quality: must be one of {sorted(VALID_QUALITY)}, got {quality!r}")

    return errors


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # order_id -- ORD-YYYY-NNNNN
    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_RE.match(oid):
        errors.append(f"order_id: must match 'ORD-YYYY-NNNNN', got {oid!r}")

    # count -- non-negative int
    count = payload.get("count")
    if not isinstance(count, int) or count < 0:
        errors.append(f"count: must be non-negative integer, got {count!r}")

    # readings -- list
    readings = payload.get("readings")
    if not isinstance(readings, list):
        errors.append(f"readings: must be array, got {type(readings).__name__}")
    else:
        if isinstance(count, int) and count != len(readings):
            errors.append(f"count={count} does not match len(readings)={len(readings)}")
        for i, r in enumerate(readings):
            errors.extend(_validate_reading(r, i))

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c3_historian.py '<json_string>'")
        print("       python validate_c3_historian.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C3 (HistorianResponse)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
