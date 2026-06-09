"""
contracts/validators/validate_c6_production_order.py

Validates a ProductionOrder payload (Contract C6) against the schema
defined in interface-contracts.md C6 and DOMAIN-MODEL.md Sec.1.1.

Usage:
    python validate_c6_production_order.py '{"order_id": "...", ...}'
    python validate_c6_production_order.py --file sample_order.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


ORDER_ID_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
MATERIAL_ID_RE = re.compile(r"^MAT-\d{4}$")
OVEN_RE = re.compile(r"^oven-\d{2}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

VALID_STATUSES = {"CREATED", "RELEASED", "IN_PROGRESS", "CONFIRMED", "ABORTED", "CLOSED"}
VALID_PLANTS = {"regensburg", "kirchheim"}

REQUIRED_FIELDS = {
    "order_id", "material_id", "plant", "oven_id",
    "planned_start", "planned_end", "standard_cycle_minutes",
    "status", "operator_id", "actual_start", "actual_end",
    "sap_confirmation_number", "goods_movement_posted",
    "created_at", "updated_at",
}


def validate(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_ID_RE.match(oid):
        errors.append(f"order_id: must match ORD-YYYY-NNNNN, got {oid!r}")

    mid = payload.get("material_id")
    if not isinstance(mid, str) or not MATERIAL_ID_RE.match(mid):
        errors.append(f"material_id: must match MAT-NNNN, got {mid!r}")

    plant = payload.get("plant")
    if plant not in VALID_PLANTS:
        errors.append(f"plant: must be one of {VALID_PLANTS}, got {plant!r}")

    oven = payload.get("oven_id")
    if not isinstance(oven, str) or not OVEN_RE.match(oven):
        errors.append(f"oven_id: must match oven-NN, got {oven!r}")

    for ts_field in ("planned_start", "planned_end", "created_at", "updated_at"):
        ts = payload.get(ts_field)
        if not isinstance(ts, str) or not ISO_RE.match(ts):
            errors.append(f"{ts_field}: must be ISO 8601 UTC (Z suffix), got {ts!r}")

    for nullable_ts in ("actual_start", "actual_end"):
        ts = payload.get(nullable_ts)
        if ts is not None and (not isinstance(ts, str) or not ISO_RE.match(ts)):
            errors.append(f"{nullable_ts}: must be ISO 8601 UTC (Z suffix) or null, got {ts!r}")

    status = payload.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status: must be one of {VALID_STATUSES}, got {status!r}")

    scm = payload.get("standard_cycle_minutes")
    if not isinstance(scm, int) or scm <= 0:
        errors.append(f"standard_cycle_minutes: must be positive int, got {scm!r}")

    gmp = payload.get("goods_movement_posted")
    if not isinstance(gmp, bool):
        errors.append(f"goods_movement_posted: must be bool, got {type(gmp).__name__}")

    for nullable_str in ("operator_id", "sap_confirmation_number"):
        v = payload.get(nullable_str)
        if v is not None and not isinstance(v, str):
            errors.append(f"{nullable_str}: must be string or null, got {type(v).__name__}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c6_production_order.py '<json_string>'")
        print("       python validate_c6_production_order.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C6 (ProductionOrder)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
