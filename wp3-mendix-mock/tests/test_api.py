"""Tests for api.py -- FastAPI endpoints via TestClient with mocked external clients."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import app, init_app
from src.exceptions import SAPClientError, WP1ClientError, WP5ClientError
from src.models import MaterialSpec
from src.order_service import OrderService
from src.sap_client import SAPClient
from src.simatic_client import SimaticClient
from src.wp1_client import WP1Client
from src.wp5_client import WP5Client


_SAP_ORDER = {
    "order_id": "ORD-2026-00001",
    "material_id": "MAT-0001",
    "plant": "regensburg",
    "oven_id": "oven-01",
    "status": "RELEASED",
}

_MATERIAL = MaterialSpec(
    material_id="MAT-0001",
    material_description="Power Transformer 100MVA",
    target_moisture_ppm=300,
    target_temperature_degC=130.0,
    target_vacuum_mbar=5.0,
    standard_cycle_minutes=480,
    max_cycle_minutes=600,
    weight_kg=8500.0,
)

_SAP_CONF_RESP = {
    "order_id": "ORD-2026-00001",
    "sap_confirmation_number": "CONF-2026-00001",
    "status": "CONFIRMED",
    "posted_at": "2026-06-09T14:00:03.000Z",
}

_GM_RESP = {
    "document_number": "GR-2026-00001",
    "posted_at": "2026-06-09T14:00:05Z",
    "status": "posted",
}


@pytest.fixture()
def svc():
    return OrderService()


@pytest.fixture()
def mock_sap(monkeypatch):
    client = SAPClient("http://sap-mock")
    monkeypatch.setattr(client, "get_order", lambda order_id: _SAP_ORDER)
    monkeypatch.setattr(client, "get_orders", lambda status=None, plant=None: [_SAP_ORDER])
    monkeypatch.setattr(client, "get_material", lambda material_id: _MATERIAL)
    monkeypatch.setattr(client, "post_confirmation", lambda req: _SAP_CONF_RESP)
    monkeypatch.setattr(client, "post_goods_movement", lambda req: _GM_RESP)
    return client


@pytest.fixture()
def mock_wp1(monkeypatch):
    client = WP1Client("http://wp1-mock")
    monkeypatch.setattr(client, "start_cycle", lambda **kwargs: None)
    return client


@pytest.fixture()
def mock_wp5(monkeypatch):
    client = WP5Client("http://wp5-mock/events")
    monkeypatch.setattr(client, "post_event", lambda event: None)
    return client


@pytest.fixture()
def mock_simatic(monkeypatch):
    client = SimaticClient("http://simatic-mock")
    monkeypatch.setattr(client, "get_process_state", lambda oven_id: {
        "oven_id": oven_id, "status": "idle", "order_id": None,
        "temperature_degC": None, "vacuum_mbar": None, "moisture_ppm": None,
        "cycle_elapsed_minutes": None, "moisture_threshold_met": None,
        "timestamp": "2026-06-09T08:00:00.000Z",
    })
    return client


@pytest.fixture(autouse=True)
def fresh_app(svc, mock_sap, mock_wp1, mock_wp5, mock_simatic):
    init_app(svc, mock_sap, mock_simatic, mock_wp1, mock_wp5, oven_id="oven-01")


@pytest.fixture()
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_flat_json(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["service"] == "wp3-mendix-mock"
        assert "order_count" in body


class TestGetOrderState:
    def test_404_for_unknown_order(self, client):
        resp = client.get("/orders/ORD-UNKNOWN/state")
        assert resp.status_code == 404

    def test_returns_c4_response_for_known_order(self, client, svc):
        svc.upsert_from_sap(_SAP_ORDER)
        resp = client.get("/orders/ORD-2026-00001/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == "ORD-2026-00001"
        assert body["status"] == "released"
        assert body["operator_id"] is None
        assert body["cycle_confirmed_at"] is None
        assert body["quality_check_passed"] is None


class TestStartOrder:
    def test_start_transitions_to_in_progress(self, client):
        resp = client.post(
            "/orders/ORD-2026-00001/start",
            json={"operator_id": "OP-007"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in-progress"

    def test_fetches_order_from_sap_if_not_in_store(self, client):
        resp = client.post(
            "/orders/ORD-2026-00001/start",
            json={"operator_id": "OP-007"},
        )
        assert resp.status_code == 200

    def test_409_on_double_start(self, client):
        client.post("/orders/ORD-2026-00001/start", json={"operator_id": "OP-007"})
        resp = client.post("/orders/ORD-2026-00001/start", json={"operator_id": "OP-007"})
        assert resp.status_code == 409

    def test_422_on_empty_operator_id(self, client):
        resp = client.post("/orders/ORD-2026-00001/start", json={"operator_id": ""})
        assert resp.status_code == 422

    def test_wp1_failure_is_non_fatal(self, client, monkeypatch, mock_wp1):
        monkeypatch.setattr(mock_wp1, "start_cycle", lambda **kwargs: (_ for _ in ()).throw(WP1ClientError("down")))
        resp = client.post("/orders/ORD-2026-00001/start", json={"operator_id": "OP-007"})
        assert resp.status_code == 200

    def test_wp5_failure_is_non_fatal(self, client, monkeypatch, mock_wp5):
        monkeypatch.setattr(mock_wp5, "post_event", lambda event: (_ for _ in ()).throw(WP5ClientError("down")))
        resp = client.post("/orders/ORD-2026-00001/start", json={"operator_id": "OP-007"})
        assert resp.status_code == 200


class TestConfirmOrder:
    def _start(self, client):
        client.post("/orders/ORD-2026-00001/start", json={"operator_id": "OP-007"})

    def test_confirm_transitions_to_closed(self, client):
        self._start(client)
        resp = client.post(
            "/orders/ORD-2026-00001/confirm",
            json={"quality_check_passed": True, "final_moisture_ppm": 275.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "closed"
        assert body["sap_confirmation_number"] == "CONF-2026-00001"

    def test_404_if_order_not_in_store(self, client):
        resp = client.post(
            "/orders/ORD-UNKNOWN/confirm",
            json={"quality_check_passed": True, "final_moisture_ppm": 200.0},
        )
        assert resp.status_code == 404

    def test_409_if_not_in_progress(self, client, svc):
        svc.upsert_from_sap(_SAP_ORDER)  # stays in released
        resp = client.post(
            "/orders/ORD-2026-00001/confirm",
            json={"quality_check_passed": True, "final_moisture_ppm": 200.0},
        )
        assert resp.status_code == 409

    def test_502_if_sap_confirmation_fails(self, client, monkeypatch, mock_sap):
        self._start(client)
        monkeypatch.setattr(mock_sap, "post_confirmation", lambda req: (_ for _ in ()).throw(SAPClientError("sap down")))
        resp = client.post(
            "/orders/ORD-2026-00001/confirm",
            json={"quality_check_passed": True, "final_moisture_ppm": 275.0},
        )
        assert resp.status_code == 502

    def test_422_on_negative_moisture(self, client):
        self._start(client)
        resp = client.post(
            "/orders/ORD-2026-00001/confirm",
            json={"quality_check_passed": True, "final_moisture_ppm": -1.0},
        )
        assert resp.status_code == 422


class TestListOrders:
    def test_returns_list(self, client, svc):
        svc.upsert_from_sap(_SAP_ORDER)
        resp = client.get("/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert any(o["order_id"] == "ORD-2026-00001" for o in body)


class TestSimaticProxy:
    def test_proxies_simatic_response(self, client):
        resp = client.get("/simatic-proxy/oven-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["oven_id"] == "oven-01"
        assert "status" in body


class TestOperatorUI:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Operator Console" in resp.text
