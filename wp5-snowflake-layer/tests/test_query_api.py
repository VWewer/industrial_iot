from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.snowflake_client as sf_module
from src.ingestion.mes_webhook import router as mes_router
from src.query_api import router as query_router

_app = FastAPI()
_app.include_router(query_router)
_app.include_router(mes_router)

client = TestClient(_app, raise_server_exceptions=True)


class TestHealth:
    def test_health_connected(self, mock_sf):
        mock_sf.is_connected.return_value = True
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "wp5-snowflake-layer"
        assert body["snowflake_connected"] is True

    def test_health_disconnected(self, mock_sf):
        mock_sf.is_connected.return_value = False
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["snowflake_connected"] is False


class TestListCycles:
    def test_empty_gold_returns_empty_list(self, mock_sf):
        mock_sf.fetchall.return_value = []
        resp = client.get("/gold/cycles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rows_returned_as_list(self, mock_sf):
        mock_sf.fetchall.return_value = [
            {"order_id": "ORD-2026-00042", "material_id": "MAT-0001", "plant": "regensburg", "oven_id": "oven-01"},
        ]
        resp = client.get("/gold/cycles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["order_id"] == "ORD-2026-00042"


class TestGetCycle:
    def test_not_found_returns_404(self, mock_sf):
        mock_sf.fetchone.return_value = None
        resp = client.get("/gold/cycles/ORD-2026-00099")
        assert resp.status_code == 404

    def test_found_includes_sensor_readings(self, mock_sf):
        mock_sf.fetchone.return_value = {
            "order_id": "ORD-2026-00042",
            "material_id": "MAT-0001",
            "plant": "regensburg",
            "oven_id": "oven-01",
        }
        mock_sf.fetchall.return_value = [
            {"reading_id": "r1", "sensor_type": "temperature", "value": 120.0},
        ]
        resp = client.get("/gold/cycles/ORD-2026-00042")
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == "ORD-2026-00042"
        assert len(body["sensor_readings"]) == 1
        assert body["sensor_readings"][0]["sensor_type"] == "temperature"


class TestListEfficiency:
    def test_empty_returns_empty_list(self, mock_sf):
        mock_sf.fetchall.return_value = []
        resp = client.get("/gold/efficiency")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_efficiency_rows_returned(self, mock_sf):
        mock_sf.fetchall.return_value = [
            {"material_id": "MAT-0001", "total_cycles": 5, "avg_delta_minutes": -10.2},
        ]
        resp = client.get("/gold/efficiency")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["material_id"] == "MAT-0001"
        assert data[0]["total_cycles"] == 5


class TestMESWebhook:
    def test_valid_cycle_started_returns_accepted(self, mock_sf):
        resp = client.post("/events", json={
            "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "event_type": "cycle_started",
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
            "operator_id": "OP-007",
            "timestamp": "2026-06-03T06:05:00Z",
            "payload": {"setpoint_temperature_degC": 130.0},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["event_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        mock_sf.execute_many.assert_called_once()

    def test_missing_required_field_returns_422(self, mock_sf):
        resp = client.post("/events", json={
            "event_type": "cycle_started",
            "oven_id": "oven-01",
            "timestamp": "2026-06-03T06:05:00Z",
            # missing event_id and order_id
        })
        assert resp.status_code == 422

    def test_invalid_event_type_returns_422(self, mock_sf):
        resp = client.post("/events", json={
            "event_id": "id",
            "event_type": "unknown_type",
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
            "timestamp": "2026-06-03T06:05:00Z",
        })
        assert resp.status_code == 422

    def test_snowflake_error_returns_503(self, mock_sf):
        from src.exceptions import SnowflakeQueryError

        mock_sf.execute_many.side_effect = SnowflakeQueryError("insert failed")
        resp = client.post("/events", json={
            "event_id": "id",
            "event_type": "cycle_confirmed",
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
            "timestamp": "2026-06-03T14:00:00Z",
        })
        assert resp.status_code == 503
