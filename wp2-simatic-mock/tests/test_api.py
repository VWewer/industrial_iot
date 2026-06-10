"""Tests for api.py -- FastAPI endpoints via TestClient."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.api import app, init_app
from src.historian import Historian
from src.models import SensorReading


def _reading(
    oven_id: str = "oven-01",
    sensor_type: str = "temperature",
    value: float = 100.0,
    order_id: str | None = "ORD-2026-00001",
    ts: str = "2026-06-01T08:00:00.000Z",
) -> SensorReading:
    return SensorReading(
        reading_id=str(uuid.uuid4()),
        timestamp_opc=ts,
        timestamp_mqtt=ts,
        plant="regensburg",
        oven_id=oven_id,
        sensor_type=sensor_type,
        value=value,
        unit="degC",
        quality="Good",
        order_id=order_id,
    )


@pytest.fixture(autouse=True)
def fresh_historian():
    h = Historian(max_readings=100)
    init_app(h, moisture_threshold=500.0, max_cycle_minutes=600.0)
    return h


@pytest.fixture()
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_body_is_flat_json(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "wp2-simatic-mock"
        assert "known_ovens" in body

    def test_known_ovens_updates_after_reading(self, client, fresh_historian):
        fresh_historian.add(_reading(oven_id="oven-01"))
        resp = client.get("/health")
        assert "oven-01" in resp.json()["known_ovens"]


class TestProcessStateEndpoint:
    def test_idle_for_unknown_oven(self, client):
        resp = client.get("/process-state/oven-99")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "idle"
        assert body["order_id"] is None

    def test_running_when_order_active(self, client, fresh_historian):
        fresh_historian.add(_reading(sensor_type="temperature", value=120.0))
        fresh_historian.add(_reading(sensor_type="moisture", value=2000.0))
        resp = client.get("/process-state/oven-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["order_id"] == "ORD-2026-00001"

    def test_cycle_complete_when_moisture_below_threshold(self, client, fresh_historian):
        fresh_historian.add(_reading(sensor_type="temperature", value=120.0))
        fresh_historian.add(_reading(sensor_type="moisture", value=200.0))
        resp = client.get("/process-state/oven-01")
        assert resp.json()["status"] == "cycle_complete"

    def test_response_fields_present(self, client, fresh_historian):
        fresh_historian.add(_reading(sensor_type="temperature", value=118.5))
        fresh_historian.add(_reading(sensor_type="vacuum", value=4.9))
        fresh_historian.add(_reading(sensor_type="moisture", value=1200.0))
        resp = client.get("/process-state/oven-01")
        body = resp.json()
        assert body["temperature_degC"] == 118.5
        assert body["vacuum_mbar"] == 4.9
        assert body["moisture_ppm"] == 1200.0
        assert body["moisture_threshold_met"] is False
        assert "timestamp" in body

    def test_response_timestamp_is_iso8601(self, client):
        import re
        resp = client.get("/process-state/oven-01")
        ts = resp.json()["timestamp"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$", ts)


class TestHistorianEndpoint:
    def _populate(self, h: Historian, order_id: str = "ORD-2026-00001") -> None:
        for i in range(5):
            h.add(_reading(
                sensor_type="temperature",
                value=float(80 + i * 10),
                order_id=order_id,
                ts=f"2026-06-01T08:00:{i * 5:02d}.000Z",
            ))
        for i in range(3):
            h.add(_reading(
                sensor_type="moisture",
                value=float(2000 - i * 100),
                order_id=order_id,
                ts=f"2026-06-01T08:00:{i * 5:02d}.000Z",
            ))

    def test_returns_all_readings_for_order(self, client, fresh_historian):
        self._populate(fresh_historian)
        resp = client.get("/historian?order_id=ORD-2026-00001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_id"] == "ORD-2026-00001"
        assert body["count"] == 8
        assert len(body["readings"]) == 8

    def test_sensor_type_filter(self, client, fresh_historian):
        self._populate(fresh_historian)
        resp = client.get("/historian?order_id=ORD-2026-00001&sensor_type=moisture")
        body = resp.json()
        assert body["count"] == 3
        assert all(r["sensor_type"] == "moisture" for r in body["readings"])

    def test_empty_for_unknown_order(self, client, fresh_historian):
        self._populate(fresh_historian)
        resp = client.get("/historian?order_id=ORD-2026-99999")
        assert resp.json()["count"] == 0

    def test_limit_param(self, client, fresh_historian):
        self._populate(fresh_historian)
        resp = client.get("/historian?order_id=ORD-2026-00001&limit=2")
        assert len(resp.json()["readings"]) == 2

    def test_order_id_required(self, client):
        resp = client.get("/historian")
        assert resp.status_code == 422
