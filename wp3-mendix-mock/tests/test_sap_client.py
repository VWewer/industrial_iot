"""Tests for sap_client.py -- HTTP calls to WP4 mocked with httpx transports."""
from __future__ import annotations

import json

import httpx
import pytest

from src.exceptions import SAPClientError
from src.models import GoodsMovementRequest, SAPConfirmationRequest
from src.sap_client import SAPClient


def _mock_transport(status: int, body: dict | list) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)
    return httpx.MockTransport(handler)


def _client(status: int = 200, body: dict | list = {}) -> SAPClient:
    c = SAPClient("http://sap-mock")
    # Patch the httpx.get / httpx.post calls -- we override via monkeypatch in each test
    return c


class TestGetOrders:
    def test_returns_list(self, monkeypatch):
        orders = [{"order_id": "ORD-2026-00001", "material_id": "MAT-0001",
                   "plant": "regensburg", "oven_id": "oven-01", "status": "RELEASED"}]
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(200, json={"count": 1, "value": orders})
        monkeypatch.setattr(httpx, "get", fake_get)
        client = SAPClient("http://sap-mock")
        result = client.get_orders(status="RELEASED")
        assert len(result) == 1
        assert result[0]["order_id"] == "ORD-2026-00001"

    def test_raises_on_http_error(self, monkeypatch):
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(503, json={"error": "unavailable"})
        monkeypatch.setattr(httpx, "get", fake_get)
        client = SAPClient("http://sap-mock")
        with pytest.raises(SAPClientError):
            client.get_orders()


class TestGetOrder:
    def test_returns_order_dict(self, monkeypatch):
        order = {"order_id": "ORD-2026-00001", "material_id": "MAT-0001",
                 "plant": "regensburg", "oven_id": "oven-01", "status": "RELEASED"}
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(200, json=order)
        monkeypatch.setattr(httpx, "get", fake_get)
        client = SAPClient("http://sap-mock")
        result = client.get_order("ORD-2026-00001")
        assert result["order_id"] == "ORD-2026-00001"

    def test_raises_on_404(self, monkeypatch):
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(404, json={"detail": "not found"})
        monkeypatch.setattr(httpx, "get", fake_get)
        client = SAPClient("http://sap-mock")
        with pytest.raises(SAPClientError):
            client.get_order("ORD-MISSING")


class TestGetMaterial:
    _material = {
        "material_id": "MAT-0001",
        "material_description": "Power Transformer 100MVA",
        "insulation_class": "H",
        "target_moisture_ppm": 300,
        "standard_cycle_minutes": 480,
        "max_cycle_minutes": 600,
        "target_temperature_degC": 130.0,
        "target_vacuum_mbar": 5.0,
        "weight_kg": 8500.0,
        "updated_at": "2026-06-01T00:00:00Z",
    }

    def test_returns_material_spec(self, monkeypatch):
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(200, json=self._material)
        monkeypatch.setattr(httpx, "get", fake_get)
        client = SAPClient("http://sap-mock")
        spec = client.get_material("MAT-0001")
        assert spec.material_id == "MAT-0001"
        assert spec.target_moisture_ppm == 300
        assert spec.target_temperature_degC == 130.0

    def test_raises_on_error(self, monkeypatch):
        def fake_get(url, params=None, timeout=None):
            return httpx.Response(404, json={})
        monkeypatch.setattr(httpx, "get", fake_get)
        with pytest.raises(SAPClientError):
            SAPClient("http://sap-mock").get_material("MAT-MISSING")


class TestPostConfirmation:
    _req = SAPConfirmationRequest(
        order_id="ORD-2026-00001",
        operation_id="ORD-2026-00001-OPR-010",
        confirmed_quantity=1.0,
        actual_start="2026-06-09T06:00:00.000Z",
        actual_end="2026-06-09T14:00:00.000Z",
        operator_id="OP-007",
        final_moisture_ppm=275.0,
        spec_met=True,
    )

    def test_returns_confirmation_dict(self, monkeypatch):
        resp_body = {"order_id": "ORD-2026-00001", "sap_confirmation_number": "CONF-2026-00001",
                     "status": "CONFIRMED", "posted_at": "2026-06-09T14:00:03.000Z"}
        def fake_post(url, json=None, timeout=None):
            return httpx.Response(200, json=resp_body)
        monkeypatch.setattr(httpx, "post", fake_post)
        client = SAPClient("http://sap-mock")
        result = client.post_confirmation(self._req)
        assert result["sap_confirmation_number"] == "CONF-2026-00001"

    def test_raises_on_http_error(self, monkeypatch):
        def fake_post(url, json=None, timeout=None):
            return httpx.Response(500, json={"error": "server error"})
        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(SAPClientError):
            SAPClient("http://sap-mock").post_confirmation(self._req)


class TestPostGoodsMovement:
    _req = GoodsMovementRequest(
        order_id="ORD-2026-00001",
        material_id="MAT-0001",
        posting_date="2026-06-09",
    )

    def test_returns_gm_dict(self, monkeypatch):
        resp_body = {"document_number": "GR-2026-00001", "posted_at": "2026-06-09T14:00:05Z", "status": "posted"}
        def fake_post(url, json=None, timeout=None):
            return httpx.Response(200, json=resp_body)
        monkeypatch.setattr(httpx, "post", fake_post)
        client = SAPClient("http://sap-mock")
        result = client.post_goods_movement(self._req)
        assert result["document_number"] == "GR-2026-00001"

    def test_raises_on_http_error(self, monkeypatch):
        def fake_post(url, json=None, timeout=None):
            return httpx.Response(502, json={})
        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(SAPClientError):
            SAPClient("http://sap-mock").post_goods_movement(self._req)
