"""
contracts/validators/run_wp3_phase4_check.py

WP3 Phase 4 producer-side seam check.

Uses FastAPI TestClient against WP3 with a real SAPClient pointed at WP4
(localhost:8003). WP1 and WP5 clients use no-op stubs so only WP4 is needed.

Contracts checked:
  C4 -- GET /orders/{order_id}/state         (order state)
  C10 -- POST /events webhook to WP5         (MES cycle events)

Also validates the full workflow: start -> confirm -> closed.

Requires WP4 running at localhost:8003. Skips gracefully if unavailable.

Usage (from project root):
  .venv/Scripts/python contracts/validators/run_wp3_phase4_check.py

Exit code 0 = all checks passed, 1 = one or more failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "wp3-mendix-mock"))

try:
    import httpx
    from fastapi.testclient import TestClient
    from src.api import app, init_app
    from src.order_service import OrderService
    from src.sap_client import SAPClient
    from src.simatic_client import SimaticClient
    from src.wp1_client import WP1Client
    from src.wp5_client import WP5Client
    from src.models import CycleEvent
except ImportError as exc:
    print(f"ERROR: missing dependency -- {exc}")
    sys.exit(1)

from validate_c4_order_state import validate as validate_c4
from validate_c10_cycle_event import validate as validate_c10

SAP_URL = "http://localhost:8003"
ORDER_ID = "ORD-2026-00042"  # RELEASED in WP4 seed data

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, list[str]]] = []
captured_events: list[dict] = []


def _sap_available() -> bool:
    try:
        resp = httpx.get(f"{SAP_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def check(label: str, payload: dict, validator) -> None:
    errors = validator(payload)
    status = PASS if not errors else FAIL
    results.append((label, status, errors))
    marker = "+" if status == PASS else "!"
    print(f"  [{marker}] {label}")
    for e in errors:
        print(f"      ERROR: {e}")


def main() -> None:
    print("\nWP3 Phase 4 -- Producer-side seam check")
    print("=" * 52)

    if not _sap_available():
        print("\nSKIP: WP4 SAP mock not available at localhost:8003")
        print("Start WP4 first: cd wp4-sap-mock && python -m src.main")
        sys.exit(0)

    print(f"  WP4 available at {SAP_URL}")

    # No-op WP1 and WP5 clients -- WP4 is the only real dependency
    class _NoopWP1(WP1Client):
        def start_cycle(self, **kwargs) -> None:
            pass

    class _CapturingWP5(WP5Client):
        def post_event(self, event: CycleEvent) -> None:
            captured_events.append(event.to_dict())

    sap = SAPClient(SAP_URL)
    init_app(
        order_service=OrderService(),
        sap_client=sap,
        simatic_client=SimaticClient("http://localhost:8001"),
        wp1_client=_NoopWP1("http://localhost:8080"),
        wp5_client=_CapturingWP5("http://localhost:8005/events"),
        oven_id="oven-01",
    )
    client = TestClient(app)

    # --- health ---
    print("\n/health")
    r = client.get("/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body["status"] == "ok"
    print(f"  [+] /health -- status=ok, order_count={body.get('order_count')}")

    # --- C4: order state (released) ---
    print("\nC4 -- /orders/{order_id}/state (released)")
    r = client.post(f"/orders/{ORDER_ID}/start", json={"operator_id": "OP-007"})
    assert r.status_code == 200, f"start failed: {r.status_code} {r.text}"

    r = client.get(f"/orders/{ORDER_ID}/state")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    state_body = r.json()
    assert state_body["status"] == "in-progress", f"Expected in-progress, got {state_body['status']}"
    check("C4 order state (in-progress)", state_body, validate_c4)

    # --- C10: cycle_started event ---
    print("\nC10 -- cycle_started event (captured from WP5 client)")
    assert len(captured_events) >= 1, f"Expected at least 1 C10 event, got {len(captured_events)}"
    started_events = [e for e in captured_events if e.get("event_type") == "cycle_started"]
    assert started_events, "No cycle_started event captured"
    check("C10 cycle_started event", started_events[0], validate_c10)

    # --- Full workflow: confirm -> closed ---
    print("\nC4 + C10 -- confirm workflow")
    r = client.post(
        f"/orders/{ORDER_ID}/confirm",
        json={"quality_check_passed": True, "final_moisture_ppm": 275.0},
    )
    assert r.status_code == 200, f"confirm failed: {r.status_code} {r.text}"
    confirm_body = r.json()
    assert confirm_body["status"] == "closed", f"Expected closed, got {confirm_body['status']}"
    assert confirm_body.get("sap_confirmation_number", "") != "", "Missing sap_confirmation_number"

    r = client.get(f"/orders/{ORDER_ID}/state")
    assert r.status_code == 200
    state_body = r.json()
    check("C4 order state (closed)", state_body, validate_c4)

    # --- C10: cycle_confirmed event ---
    confirmed_events = [e for e in captured_events if e.get("event_type") == "cycle_confirmed"]
    assert confirmed_events, "No cycle_confirmed event captured"
    check("C10 cycle_confirmed event", confirmed_events[0], validate_c10)

    # --- Summary ---
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)

    print(f"\n  C10 events captured: {[e['event_type'] for e in captured_events]}")
    print(f"  SAP confirmation: {confirm_body.get('sap_confirmation_number')}")

    print("\n" + "=" * 52)
    print(f"Result: {passed}/{total} checks passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- WP3 Phase 4 producer seam check PASSED")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
