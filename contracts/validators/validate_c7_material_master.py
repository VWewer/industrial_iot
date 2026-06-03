"""
contracts/validators/validate_c7_material_master.py

Validates a MaterialMaster payload (Contract C7) against the schema
defined in interface-contracts.md C7 and DOMAIN-MODEL.md Sec.1.2.

Usage:
    python validate_c7_material_master.py '{"material_id": "...", ...}'
    python validate_c7_material_master.py --file sample_material.json

Exit code 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


MATERIAL_ID_RE = re.compile(r"^MAT-\d{4}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
VALID_INSULATION_CLASSES = {"A", "B", "F", "H"}

REQUIRED_FIELDS = {
    "material_id", "material_description", "insulation_class",
    "target_moisture_ppm", "standard_cycle_minutes", "max_cycle_minutes",
    "target_temperature_degC", "target_vacuum_mbar", "weight_kg", "updated_at",
}


def validate(payload: dict[str, Any]) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    mid = payload.get("material_id")
    if not isinstance(mid, str) or not MATERIAL_ID_RE.match(mid):
        errors.append(f"material_id: must match MAT-NNNN, got {mid!r}")

    desc = payload.get("material_description")
    if not isinstance(desc, str) or not desc:
        errors.append(f"material_description: must be non-empty string, got {desc!r}")

    ic = payload.get("insulation_class")
    if ic not in VALID_INSULATION_CLASSES:
        errors.append(f"insulation_class: must be one of {VALID_INSULATION_CLASSES}, got {ic!r}")

    for int_field in ("target_moisture_ppm", "standard_cycle_minutes", "max_cycle_minutes"):
        v = payload.get(int_field)
        if not isinstance(v, int) or v <= 0:
            errors.append(f"{int_field}: must be positive int, got {v!r}")

    scm = payload.get("standard_cycle_minutes", 0)
    mcm = payload.get("max_cycle_minutes", 0)
    if isinstance(scm, int) and isinstance(mcm, int) and mcm <= scm:
        errors.append(f"max_cycle_minutes ({mcm}) must be > standard_cycle_minutes ({scm})")

    for float_field in ("target_temperature_degC", "target_vacuum_mbar", "weight_kg"):
        v = payload.get(float_field)
        if not isinstance(v, (int, float)) or v <= 0:
            errors.append(f"{float_field}: must be positive numeric, got {v!r}")

    ts = payload.get("updated_at")
    if not isinstance(ts, str) or not ISO_RE.match(ts):
        errors.append(f"updated_at: must be ISO 8601 UTC (Z suffix), got {ts!r}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_c7_material_master.py '<json_string>'")
        print("       python validate_c7_material_master.py --file sample.json")
        sys.exit(1)

    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.argv[1])

    errors = validate(payload)

    if not errors:
        print("PASS -- payload matches Contract C7 (MaterialMaster)")
        sys.exit(0)
    else:
        print(f"FAIL -- {len(errors)} error(s) found:")
        for e in errors:
            print(f"  * {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
