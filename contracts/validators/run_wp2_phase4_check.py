"""
contracts/validators/run_wp2_phase4_check.py

WP2 Phase 4 producer-side seam check.

Starts WP2 via FastAPI TestClient (no server needed), seeds the historian
with known readings, calls all contract endpoints, and validates each
response against its contract validator.

Contracts checked:
  C2 -- GET /process-state/{oven_id}   (process state)
  C3 -- GET /historian?order_id=...    (time-series query)

Usage (from project root):
  .venv/Scripts/python contracts/validators/run_wp2_phase4_check.py

Exit code 0 = all checks passed, 1 = one or more failed.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "wp2-simatic-mock"))

from fastapi.testclient import TestClient

from src.api import app, init_app
from src.historian import Historian
from src.models import SensorReading

from validate_c2_process_state import validate as validate_c2
from validate_c3_historian import validate as validate_c3

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, list[str]]] = []

OVEN_ID = "oven-01"
ORDER_ID = "ORD-2026-00001"


def _ts(offset_s: int = 0) -> str:
    dt = datetime(2026, 6, 10, 8, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _reading(sensor_type: str, value: float, unit: str, offset_s: int = 0) -> SensorReading:
    ts = _ts(offset_s)
    return SensorReading(
        reading_id=str(uuid.uuid4()),
        timestamp_opc=ts,
        timestamp_mqtt=ts,
        plant="regensburg",
        oven_id=OVEN_ID,
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        quality="Good",
        order_id=ORDER_ID,
    )


def check(label: str, payload: dict, validator) -> None:
    errors = validator(payload)
    status = PASS if not errors else FAIL
    results.append((label, status, errors))
    marker = "+" if status == PASS else "!"
    print(f"  [{marker}] {label}")
    for e in errors:
        print(f"      ERROR: {e}")


def main() -> None:
    historian = Historian(max_readings=500)

    # Seed with 5 readings per channel so historian is non-empty
    for i in range(5):
        historian.add(_reading("temperature", 80.0 + i * 10, "degC", offset_s=i * 30))
        historian.add(_reading("vacuum", 10.0 - i * 1.5, "mbar", offset_s=i * 30))
        historian.add(_reading("moisture", 2000.0 - i * 200, "ppm", offset_s=i * 30))

    init_app(historian, moisture_threshold=500.0, max_cycle_minutes=600.0, oven_id=OVEN_ID)
    client = TestClient(app)

    print("\nWP2 Phase 4 -- Producer-side seam check")
    print("=" * 52)

    # --- health ---
    print("\n/health")
    r = client.get("/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body["status"] == "ok", f"health.status != ok: {body}"
    print(f"  [+] /health -- status=ok, known_ovens={body.get('known_ovens')}")

    # --- C2: process state ---
    print("\nC2 -- /process-state/{oven_id}")
    r = client.get(f"/process-state/{OVEN_ID}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    check("C2 process-state (oven-01, running)", r.json(), validate_c2)

    # Idle oven (no readings)
    r = client.get("/process-state/oven-99")
    assert r.status_code == 200, f"Expected 200 for unknown oven, got {r.status_code}"
    check("C2 process-state (oven-99, idle/unknown)", r.json(), validate_c2)

    # --- C3: historian ---
    print("\nC3 -- /historian")
    r = client.get(f"/historian?order_id={ORDER_ID}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["count"] == 15, f"Expected 15 readings (5x3 sensors), got {body['count']}"
    check(f"C3 historian (order={ORDER_ID}, all sensors)", body, validate_c3)

    # With sensor_type filter
    r = client.get(f"/historian?order_id={ORDER_ID}&sensor_type=temperature")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body["count"] == 5, f"Expected 5 temperature readings, got {body['count']}"
    check(f"C3 historian (order={ORDER_ID}, sensor_type=temperature)", body, validate_c3)

    # Empty for unknown order
    r = client.get("/historian?order_id=ORD-2026-99999")
    assert r.status_code == 200, f"Expected 200 for empty result, got {r.status_code}"
    check("C3 historian (unknown order, empty result)", r.json(), validate_c3)

    # --- Summary ---
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)

    print("\n" + "=" * 52)
    print(f"Result: {passed}/{total} checks passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- WP2 Phase 4 producer seam check PASSED")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
