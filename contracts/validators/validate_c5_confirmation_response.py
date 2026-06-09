"""
contracts/validators/validate_c5_confirmation_response.py

Validates a C5 OperationConfirmation response payload against the schema
defined in interface-contracts.md C5.

Usage:
    python validate_c5_confirmation_response.py '{"order_id": "...", ...}'
    python validate_c5_confirmation_response.py --file sample_c5_response.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


ORDER_ID_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
CONF_RE = re.compile(r"^CONF-\d{4}-\d{5}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

REQUIRED_FIELDS = {"order_id", "sap_confirmation_number", "status", "posted_at"}


def validate(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_ID_RE.match(oid):
        errors.append(f"order_id: must match ORD-YYYY-NNNNN, got {oid!r}")

    conf = payload.get("sap_confirmation_number")
    if not isinstance(conf, str) or not CONF_RE.match(conf):
        errors.append(f"sap_confirmation_number: must match CONF-YYYY-NNNNN, got {conf!r}")

    status = payload.get("status")
    if status != "CONFIRMED":
        errors.append(f"status: expected 'CONFIRMED', got {status!r}")

    ts = payload.get("posted_at")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"posted_at: must be ISO 8601 UTC (Z suffix), got {ts!r}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c5_confirmation_response.py '<json_string>'")
        print("       python validate_c5_confirmation_response.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C5 (OperationConfirmation response)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
