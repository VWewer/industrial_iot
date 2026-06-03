"""
contracts/validators/validate_c12_gold_cycle.py

Validates a gold_cycle_summary row (Contract C12) against the schema
defined in DOMAIN-MODEL.md Section 6.

Usage:
    python validate_c12_gold_cycle.py '<json_string>'
    python validate_c12_gold_cycle.py --file sample_cycle.json
    python validate_c12_gold_cycle.py --seed  (validates all records in contracts/seed-data/historical_cycles.json)

Exit code 0 = all valid, 1 = any invalid.
"""

from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from typing import Any


ORDER_RE = re.compile(r"^ORD-\d{4}-\d{5}$")
MATERIAL_RE = re.compile(r"^MAT-\d{4}$")
OVEN_RE = re.compile(r"^oven-\d{2}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
VALID_PLANTS = {"regensburg", "kirchheim"}

REQUIRED_FIELDS = {
    "order_id": str,
    "material_id": str,
    "material_description": str,
    "plant": str,
    "oven_id": str,
    "cycle_start_time": str,
    "cycle_end_time": str,
    "actual_duration_minutes": (int, float),
    "standard_cycle_minutes": int,
    "delta_minutes": (int, float),
    "peak_temperature_degC": (int, float),
    "min_vacuum_mbar": (int, float),
    "final_moisture_ppm": (int, float),
    "target_moisture_ppm": int,
    "spec_met": bool,
    "sap_confirmation_number": str,
    "goods_movement_posted": bool,
}

NULLABLE_FIELDS = {"operator_id"}


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # Required fields — type check
    for field, expected in REQUIRED_FIELDS.items():
        val = row.get(field)
        if val is None:
            errors.append(f"{field}: required, missing")
            continue
        if isinstance(expected, tuple):
            if not isinstance(val, expected):
                errors.append(f"{field}: expected one of {expected}, got {type(val).__name__}")
        else:
            if not isinstance(val, expected):
                # bool is subclass of int — be explicit
                if expected is int and isinstance(val, bool):
                    errors.append(f"{field}: expected int (not bool), got bool")
                elif not isinstance(val, expected):
                    errors.append(f"{field}: expected {expected.__name__}, got {type(val).__name__}")

    # Pattern checks
    oid = row.get("order_id", "")
    if isinstance(oid, str) and not ORDER_RE.match(oid):
        errors.append(f"order_id: must match 'ORD-YYYY-NNNNN', got {oid!r}")

    mid = row.get("material_id", "")
    if isinstance(mid, str) and not MATERIAL_RE.match(mid):
        errors.append(f"material_id: must match 'MAT-NNNN', got {mid!r}")

    plant = row.get("plant", "")
    if plant not in VALID_PLANTS:
        errors.append(f"plant: must be one of {VALID_PLANTS}, got {plant!r}")

    oven = row.get("oven_id", "")
    if isinstance(oven, str) and not OVEN_RE.match(oven):
        errors.append(f"oven_id: must match 'oven-NN', got {oven!r}")

    for ts_field in ("cycle_start_time", "cycle_end_time"):
        ts = row.get(ts_field, "")
        if isinstance(ts, str) and not ISO_RE.match(ts):
            errors.append(f"{ts_field}: must be ISO 8601 UTC string, got {ts!r}")

    # Logical checks
    dur = row.get("actual_duration_minutes")
    std = row.get("standard_cycle_minutes")
    delta = row.get("delta_minutes")
    if all(isinstance(v, (int, float)) for v in [dur, std, delta]):
        expected_delta = round(dur - std)  # type: ignore
        if abs(expected_delta - delta) > 1:  # allow 1 minute rounding
            errors.append(
                f"delta_minutes inconsistent: actual({dur}) - standard({std}) = {expected_delta}, got {delta}"
            )

    final = row.get("final_moisture_ppm")
    target = row.get("target_moisture_ppm")
    spec = row.get("spec_met")
    if all(v is not None for v in [final, target, spec]):
        expected_spec = final < target  # type: ignore
        if spec != expected_spec:
            errors.append(
                f"spec_met inconsistent: final_moisture({final}) < target({target}) = {expected_spec}, got spec_met={spec}"
            )

    return errors


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--seed":
        seed_path = Path(__file__).parent.parent / "seed-data" / "historical_cycles.json"
        records = json.loads(seed_path.read_text())
        all_valid = True
        for i, record in enumerate(records):
            errors = validate(record)
            if errors:
                all_valid = False
                print(f"✗ Record {i} ({record.get('order_id', '?')}): {len(errors)} error(s)")
                for e in errors:
                    print(f"    • {e}")
            else:
                print(f"✓ Record {i} ({record.get('order_id', '?')}): valid")
        sys.exit(0 if all_valid else 1)

    elif sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            row = json.load(f)
    else:
        row = json.loads(sys.argv[1])

    errors = validate(row)
    if not errors:
        print("✓ VALID — row matches Contract C12 (gold_cycle_summary)")
        sys.exit(0)
    else:
        print(f"✗ INVALID — {len(errors)} error(s) found:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
