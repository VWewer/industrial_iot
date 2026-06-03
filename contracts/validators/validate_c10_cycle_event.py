"""
contracts/validators/validate_c10_cycle_event.py

Validates a CycleEvent payload (Contract C10) against the schema
defined in DOMAIN-MODEL.md Section 1.4.

Usage:
    python validate_c10_cycle_event.py '<json_string>'
    python validate_c10_cycle_event.py --file sample_event.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import sys
import re
from typing import Any


VALID_EVENT_TYPES = {
    "cycle_started",
    "cycle_confirmed",
    "cycle_aborted",
    "cycle_timeout",
    "sap_confirmation_failed",
}
VALID_PLANTS = {"regensburg", "kirchheim"}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
OVEN_RE = re.compile(r"^oven-\d{2}$")
ORDER_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Required payload fields per event_type
PAYLOAD_SCHEMA: dict[str, dict[str, type]] = {
    "cycle_started": {
        "setpoint_temperature_degC": float,
        "setpoint_vacuum_mbar": float,
    },
    "cycle_confirmed": {
        "sap_confirmation_number": str,
        "goods_movement_document": str,
    },
    "cycle_aborted": {
        "reason": str,
    },
    "cycle_timeout": {
        "elapsed_minutes": int,
        "max_cycle_minutes": int,
    },
    "sap_confirmation_failed": {
        "error_code": str,
        "error_message": str,
    },
}


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # event_id — UUID v4
    eid = payload.get("event_id")
    if not isinstance(eid, str) or not UUID_RE.match(eid):
        errors.append(f"event_id: must be UUID v4, got {eid!r}")

    # event_type — enum
    etype = payload.get("event_type")
    if etype not in VALID_EVENT_TYPES:
        errors.append(f"event_type: must be one of {VALID_EVENT_TYPES}, got {etype!r}")

    # order_id — ORD-YYYY-NNNNN
    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_RE.match(oid):
        errors.append(f"order_id: must match 'ORD-YYYY-NNNNN', got {oid!r}")

    # oven_id — format oven-NN
    oven = payload.get("oven_id")
    if not isinstance(oven, str) or not OVEN_RE.match(oven):
        errors.append(f"oven_id: must match 'oven-NN' format, got {oven!r}")

    # operator_id — string or null
    op = payload.get("operator_id")
    if op is not None and not isinstance(op, str):
        errors.append(f"operator_id: must be string or null, got {type(op).__name__}")

    # timestamp — ISO 8601 UTC
    ts = payload.get("timestamp")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"timestamp: must be ISO 8601 UTC string, got {ts!r}")

    # payload — validate per event_type if event_type is valid
    inner = payload.get("payload")
    if etype in PAYLOAD_SCHEMA:
        if inner is None:
            errors.append(f"payload: required for event_type={etype!r}, got null")
        elif not isinstance(inner, dict):
            errors.append(f"payload: must be object for event_type={etype!r}, got {type(inner).__name__}")
        else:
            schema = PAYLOAD_SCHEMA[etype]
            for field, expected_type in schema.items():
                val = inner.get(field)
                if val is None:
                    errors.append(f"payload.{field}: required for {etype}, missing")
                elif not isinstance(val, (expected_type, int if expected_type is float else expected_type)):
                    # allow int where float expected
                    if expected_type is float and isinstance(val, int):
                        pass
                    else:
                        errors.append(
                            f"payload.{field}: expected {expected_type.__name__}, got {type(val).__name__}"
                        )

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c10_cycle_event.py '<json_string>'")
        print("       python validate_c10_cycle_event.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("✓ VALID — payload matches Contract C10 (CycleEvent / MES webhook)")
        sys.exit(0)
    else:
        print(f"✗ INVALID — {len(errors)} error(s) found:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
