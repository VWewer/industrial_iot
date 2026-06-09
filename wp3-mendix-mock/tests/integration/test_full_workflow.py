"""Integration test: full order workflow against live WP4 (SAP mock on port 8003).

Requires WP4 running at localhost:8003.
Deselect with: pytest -m "not integration"
"""
from __future__ import annotations

import pytest

try:
    import httpx
    from fastapi.testclient import TestClient

    from src.api import app, init_app
    from src.order_service import OrderService
    from src.sap_client import SAPClient
    from src.simatic_client import SimaticClient
    from src.wp1_client import WP1Client
    from src.wp5_client import WP5Client
except ImportError:
    pytest.skip("dependencies not installed", allow_module_level=True)

SAP_URL = "http://localhost:8003"
SIMATIC_URL = "http://localhost:8001"
WP1_URL = "http://localhost:8080"
WP5_URL = "http://localhost:8005/events"

ORDER_ID = "ORD-2026-00001"


def _sap_available() -> bool:
    try:
        resp = httpx.get(f"{SAP_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def test_client():
    if not _sap_available():
        pytest.skip("WP4 SAP mock not available at localhost:8003")

    sap = SAPClient(SAP_URL)
    # WP1, WP5 may not be running -- use no-op fallback clients
    class _NoopWP1(WP1Client):
        def start_cycle(self, **kwargs): pass
    class _NoopWP5(WP5Client):
        def post_event(self, event): pass

    init_app(
        order_service=OrderService(),
        sap_client=sap,
        simatic_client=SimaticClient(SIMATIC_URL),
        wp1_client=_NoopWP1(WP1_URL),
        wp5_client=_NoopWP5(WP5_URL),
        oven_id="oven-01",
    )
    return TestClient(app)


@pytest.mark.integration
def test_start_order_against_live_sap(test_client):
    resp = test_client.post(
        f"/orders/{ORDER_ID}/start",
        json={"operator_id": "OP-007"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in-progress"


@pytest.mark.integration
def test_confirm_order_against_live_sap(test_client):
    resp = test_client.post(
        f"/orders/{ORDER_ID}/confirm",
        json={"quality_check_passed": True, "final_moisture_ppm": 275.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert body.get("sap_confirmation_number", "") != ""


@pytest.mark.integration
def test_order_state_reflects_closed(test_client):
    resp = test_client.get(f"/orders/{ORDER_ID}/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert body["quality_check_passed"] is True
