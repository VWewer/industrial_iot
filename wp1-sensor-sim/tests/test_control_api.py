"""Unit tests for the FastAPI control API."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.control_api import app, init_app
from src.exceptions import CycleAlreadyRunningError, NoCycleActiveError
from src.models import CycleState, SimulatorStatus


def _make_mock_simulator(state: CycleState = CycleState.IDLE) -> MagicMock:
    sim = MagicMock()
    sim.state = state
    sim.get_status.return_value = SimulatorStatus(
        state=state.value,
        order_id=None,
        simulated_elapsed_minutes=0.0,
        temperature_degC=25.0,
        vacuum_mbar=1013.0,
        moisture_ppm=5000.0,
    )
    return sim


@pytest.fixture(autouse=True)
def reset_simulator():
    """Inject a fresh mock simulator before each test."""
    sim = _make_mock_simulator()
    init_app(sim)
    yield sim


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_includes_simulator_state(self, client):
        response = client.get("/health")
        assert "simulator_state" in response.json()


class TestStartCycle:
    def test_start_returns_200(self, client):
        response = client.post("/control/start", json={
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
        })
        assert response.status_code == 200

    def test_start_returns_order_id(self, client):
        response = client.post("/control/start", json={
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
        })
        assert response.json()["order_id"] == "ORD-2026-00042"

    def test_start_when_running_returns_409(self, client, reset_simulator):
        reset_simulator.start_cycle.side_effect = CycleAlreadyRunningError("already running")
        response = client.post("/control/start", json={
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
        })
        assert response.status_code == 409

    def test_start_with_empty_order_id_returns_422(self, client):
        response = client.post("/control/start", json={
            "order_id": "",
            "oven_id": "oven-01",
        })
        assert response.status_code == 422

    def test_start_with_zero_moisture_target_returns_422(self, client):
        response = client.post("/control/start", json={
            "order_id": "ORD-2026-00042",
            "oven_id": "oven-01",
            "target_moisture_ppm": 0,
        })
        assert response.status_code == 422


class TestStopCycle:
    def test_stop_returns_200(self, client):
        response = client.post("/control/stop")
        assert response.status_code == 200

    def test_stop_when_idle_returns_409(self, client, reset_simulator):
        reset_simulator.stop_cycle.side_effect = NoCycleActiveError("no cycle")
        response = client.post("/control/stop")
        assert response.status_code == 409


class TestGetStatus:
    def test_status_returns_200(self, client):
        response = client.get("/control/status")
        assert response.status_code == 200

    def test_status_contains_required_fields(self, client):
        data = client.get("/control/status").json()
        assert "state" in data
        assert "order_id" in data
        assert "simulated_elapsed_minutes" in data
        assert "temperature_degC" in data
        assert "vacuum_mbar" in data
        assert "moisture_ppm" in data

    def test_status_reflects_idle_state(self, client):
        data = client.get("/control/status").json()
        assert data["state"] == "idle"
