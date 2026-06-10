"""
contracts/validators/validate_c4_order_state.py

Validates an OrderState payload (Contract C4) against the schema
defined in contracts/interface-contracts.md C4.

Usage:
    python validate_c4_order_state.py '<json_string>'
    python validate_c4_order_state.py --file sample.json

Exit code 0 = valid, 1 = invalid.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

VALID_STATUSES = {"released", "in-progress", "confirmed", "closed"}
ORDER_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # order_id -- ORD-YYYY-NNNNN
    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_RE.match(oid):
        errors.append(f"order_id: must match 'ORD-YYYY-NNNNN', got {oid!r}")

    # status -- enum
    status = payload.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status: must be one of {sorted(VALID_STATUSES)}, got {status!r}")

    # operator_id -- string or null
    op = payload.get("operator_id")
    if op is not None and not isinstance(op, str):
        errors.append(f"operator_id: must be string or null, got {type(op).__name__}")

    # cycle_confirmed_at -- ISO 8601 UTC or null
    cca = payload.get("cycle_confirmed_at")
    if cca is not None:
        if not isinstance(cca, str) or not ISO_RE.match(cca):
            errors.append(f"cycle_confirmed_at: must be ISO 8601 UTC string or null, got {cca!r}")

    # quality_check_passed -- bool or null
    qcp = payload.get("quality_check_passed")
    if qcp is not None and not isinstance(qcp, bool):
        errors.append(f"quality_check_passed: must be boolean or null, got {type(qcp).__name__}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c4_order_state.py '<json_string>'")
        print("       python validate_c4_order_state.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C4 (OrderState)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
