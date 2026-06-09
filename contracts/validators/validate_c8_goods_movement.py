"""
contracts/validators/validate_c8_goods_movement.py

Validates a GoodsMovement response payload (Contract C8) against the schema
defined in interface-contracts.md C8.

Usage:
    python validate_c8_goods_movement.py '{"document_number": "...", ...}'
    python validate_c8_goods_movement.py --file sample_gr.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


DOC_RE = re.compile(r"^GR-\d{4}-\d{6}$")
ORDER_ID_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
MATERIAL_ID_RE = re.compile(r"^MAT-\d{4}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_FIELDS = {
    "document_number", "order_id", "material_id", "movement_type",
    "quantity", "unit", "posting_date", "storage_location", "posted_at", "status",
}


def validate(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    doc = payload.get("document_number")
    if not isinstance(doc, str) or not DOC_RE.match(doc):
        errors.append(f"document_number: must match GR-YYYY-NNNNNN, got {doc!r}")

    oid = payload.get("order_id")
    if not isinstance(oid, str) or not ORDER_ID_RE.match(oid):
        errors.append(f"order_id: must match ORD-YYYY-NNNNN, got {oid!r}")

    mid = payload.get("material_id")
    if not isinstance(mid, str) or not MATERIAL_ID_RE.match(mid):
        errors.append(f"material_id: must match MAT-NNNN, got {mid!r}")

    mt = payload.get("movement_type")
    if mt != "GR_PRODUCTION":
        errors.append(f"movement_type: expected 'GR_PRODUCTION', got {mt!r}")

    qty = payload.get("quantity")
    if not isinstance(qty, (int, float)) or qty <= 0:
        errors.append(f"quantity: must be positive numeric, got {qty!r}")

    unit = payload.get("unit")
    if not isinstance(unit, str) or not unit:
        errors.append(f"unit: must be non-empty string, got {unit!r}")

    pd = payload.get("posting_date")
    if not isinstance(pd, str) or not DATE_RE.match(pd):
        errors.append(f"posting_date: must be YYYY-MM-DD, got {pd!r}")

    sl = payload.get("storage_location")
    if not isinstance(sl, str) or not sl:
        errors.append(f"storage_location: must be non-empty string, got {sl!r}")

    ts = payload.get("posted_at")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"posted_at: must be ISO 8601 UTC (Z suffix), got {ts!r}")

    status = payload.get("status")
    if status != "posted":
        errors.append(f"status: expected 'posted', got {status!r}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c8_goods_movement.py '<json_string>'")
        print("       python validate_c8_goods_movement.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C8 (GoodsMovement response)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
