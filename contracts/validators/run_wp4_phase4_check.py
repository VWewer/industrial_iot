"""
contracts/validators/run_wp4_phase4_check.py

WP4 Phase 4 producer-side seam check.

Starts WP4 via FastAPI TestClient (no server needed), calls all contract
endpoints, validates each response against its contract validator.

Contracts checked:
  C6 -- GET /odata/v1/ProductionOrders('{id}')        (single order)
  C6 -- GET /odata/v1/ProductionOrders                 (list)
  C7 -- GET /odata/v1/Materials('{id}')                (single material)
  C7 -- GET /odata/v1/Materials                        (list)
  C5 -- POST /odata/v1/OperationConfirmations          (confirmation response)
  C8 -- POST /odata/v1/GoodsMovements                  (goods movement response)

Usage (from project root):
  .venv/Scripts/python contracts/validators/run_wp4_phase4_check.py

Exit code 0 = all checks passed, 1 = one or more failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make project root importable
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "wp4-sap-mock"))

from fastapi.testclient import TestClient

from src import api as api_module
from src.data_store import DataStore
from src.main import app

from validate_c5_confirmation_response import validate as validate_c5
from validate_c6_production_order import validate as validate_c6
from validate_c7_material_master import validate as validate_c7
from validate_c8_goods_movement import validate as validate_c8


PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, list[str]]] = []


def check(label: str, payload: dict, validator) -> None:
    errors = validator(payload)
    status = PASS if not errors else FAIL
    results.append((label, status, errors))
    marker = "+" if status == PASS else "!"
    print(f"  [{marker}] {label}")
    for e in errors:
        print(f"      ERROR: {e}")


def main() -> None:
    # Wire fresh store
    store = DataStore()
    store.load_seed_data()
    api_module.store = store

    client = TestClient(app, raise_server_exceptions=True)

    print("\nWP4 Phase 4 -- Producer-side seam check")
    print("=" * 52)

    # --- C6 single order ---
    print("\nC6 -- ProductionOrders (single)")
    r = client.get("/odata/v1/ProductionOrders('ORD-2026-00042')")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    check("C6 single order (ORD-2026-00042)", r.json(), validate_c6)

    # All four seed orders
    for oid in ("ORD-2026-00041", "ORD-2026-00039", "ORD-2026-00043"):
        r = client.get(f"/odata/v1/ProductionOrders('{oid}')")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        check(f"C6 single order ({oid})", r.json(), validate_c6)

    # --- C6 list ---
    print("\nC6 -- ProductionOrders (list)")
    r = client.get("/odata/v1/ProductionOrders")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["count"] == 4, f"Expected 4 orders, got {body['count']}"
    for order in body["value"]:
        check(f"C6 list item ({order.get('order_id', '?')})", order, validate_c6)

    # --- C7 single material ---
    print("\nC7 -- Materials (single)")
    for mid in ("MAT-0001", "MAT-0002", "MAT-0003", "MAT-0004"):
        r = client.get(f"/odata/v1/Materials('{mid}')")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        check(f"C7 single material ({mid})", r.json(), validate_c7)

    # --- C7 list ---
    print("\nC7 -- Materials (list)")
    r = client.get("/odata/v1/Materials")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    for mat in body["value"]:
        check(f"C7 list item ({mat.get('material_id', '?')})", mat, validate_c7)

    # --- C5 confirmation ---
    print("\nC5 -- OperationConfirmations")
    # Use RELEASED order (ORD-2026-00042) -- can confirm from RELEASED state
    r = client.post("/odata/v1/OperationConfirmations", json={
        "order_id": "ORD-2026-00042",
        "operation_id": "ORD-2026-00042-OPR-010",
        "confirmed_quantity": 1.0,
        "actual_start": "2026-06-03T06:05:00Z",
        "actual_end": "2026-06-03T13:58:00Z",
        "operator_id": "OP-007",
        "final_moisture_ppm": 287.4,
        "spec_met": True,
    })
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    check("C5 confirmation response", r.json(), validate_c5)

    # --- C8 goods movement ---
    print("\nC8 -- GoodsMovements")
    r = client.post("/odata/v1/GoodsMovements", json={
        "order_id": "ORD-2026-00042",
        "material_id": "MAT-0001",
        "movement_type": "GR_PRODUCTION",
        "quantity": 1,
        "unit": "EA",
        "posting_date": "2026-06-03",
        "storage_location": "WH-01",
    })
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    check("C8 goods movement response", r.json(), validate_c8)

    # --- Summary ---
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)

    print("\n" + "=" * 52)
    print(f"Result: {passed}/{total} checks passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- WP4 Phase 4 producer seam check PASSED")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
