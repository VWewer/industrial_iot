"""
contracts/validators/validate_c2_process_state.py

Validates a ProcessState payload (Contract C2) against the schema
defined in contracts/interface-contracts.md C2.

Usage:
    python validate_c2_process_state.py '<json_string>'
    python validate_c2_process_state.py --file sample.json

Exit code 0 = valid, 1 = invalid.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

VALID_STATUSES = {"idle", "running", "cycle_complete", "timeout"}
OVEN_RE = re.compile(r"^oven-\d{2}$")
ORDER_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # oven_id -- format oven-NN
    oven = payload.get("oven_id")
    if not isinstance(oven, str) or not OVEN_RE.match(oven):
        errors.append(f"oven_id: must match 'oven-NN' format, got {oven!r}")

    # order_id -- string or null
    oid = payload.get("order_id")
    if oid is not None:
        if not isinstance(oid, str) or not ORDER_RE.match(oid):
            errors.append(f"order_id: must match 'ORD-YYYY-NNNNN' or null, got {oid!r}")

    # status -- enum
    status = payload.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status: must be one of {sorted(VALID_STATUSES)}, got {status!r}")

    # numeric fields -- float or null
    for field in ("temperature_degC", "vacuum_mbar", "moisture_ppm", "cycle_elapsed_minutes"):
        val = payload.get(field)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(f"{field}: must be float or null, got {type(val).__name__}")
        if field == "cycle_elapsed_minutes" and isinstance(val, (int, float)) and val < 0:
            errors.append(f"cycle_elapsed_minutes: must be >= 0, got {val}")

    # moisture_threshold_met -- bool or null
    mtm = payload.get("moisture_threshold_met")
    if mtm is not None and not isinstance(mtm, bool):
        errors.append(f"moisture_threshold_met: must be boolean or null, got {type(mtm).__name__}")

    # timestamp -- ISO 8601 UTC
    ts = payload.get("timestamp")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"timestamp: must be ISO 8601 UTC string, got {ts!r}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c2_process_state.py '<json_string>'")
        print("       python validate_c2_process_state.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C2 (ProcessState)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
