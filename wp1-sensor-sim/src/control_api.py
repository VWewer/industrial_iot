"""FastAPI control endpoints for WP1 — start, stop, status."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from .exceptions import CycleAlreadyRunningError, NoCycleActiveError, InvalidCycleConfigError
from .models import CycleConfig
from .simulator import CycleSimulator

log = logging.getLogger(__name__)

app = FastAPI(title="WP1 Sensor Simulator Control API", version="1.0.0")

# Injected at startup by main.py
_simulator: Optional[CycleSimulator] = None


def init_app(simulator: CycleSimulator) -> None:
    """Wire the simulator instance into the API. Called once at startup."""
    global _simulator
    _simulator = simulator


class StartRequest(BaseModel):
    order_id: str
    oven_id: str
    target_temperature_degC: float = 120.0
    target_vacuum_mbar: float = 5.0
    target_moisture_ppm: float = 300.0
    standard_cycle_minutes: float = 480.0
    warming_duration_minutes: float = 60.0

    @field_validator("order_id")
    @classmethod
    def order_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("order_id must not be empty")
        return v

    @field_validator("target_moisture_ppm", "standard_cycle_minutes")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be > 0")
        return v


@app.post("/control/start", status_code=200)
def start_cycle(body: StartRequest) -> dict:
    """Start a new drying cycle. Transitions simulator from IDLE → WARMING."""
    _require_simulator()
    config = CycleConfig(
        order_id=body.order_id,
        oven_id=body.oven_id,
        target_temperature_degC=body.target_temperature_degC,
        target_vacuum_mbar=body.target_vacuum_mbar,
        target_moisture_ppm=body.target_moisture_ppm,
        standard_cycle_minutes=body.standard_cycle_minutes,
        warming_duration_minutes=body.warming_duration_minutes,
    )
    try:
        _simulator.start_cycle(config)  # type: ignore[union-attr]
    except CycleAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidCycleConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    log.info("Cycle start requested via API", extra={"order_id": body.order_id})
    return {"status": "started", "order_id": body.order_id}


@app.post("/control/stop", status_code=200)
def stop_cycle() -> dict:
    """Force-stop the active cycle and return to IDLE."""
    _require_simulator()
    try:
        _simulator.stop_cycle()  # type: ignore[union-attr]
    except NoCycleActiveError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    log.info("Cycle stop requested via API")
    return {"status": "stopped"}


@app.get("/control/status", status_code=200)
def get_status() -> dict:
    """Return current simulator state and latest sensor values."""
    _require_simulator()
    status = _simulator.get_status()  # type: ignore[union-attr]
    return {
        "state": status.state,
        "order_id": status.order_id,
        "simulated_elapsed_minutes": status.simulated_elapsed_minutes,
        "temperature_degC": status.temperature_degC,
        "vacuum_mbar": status.vacuum_mbar,
        "moisture_ppm": status.moisture_ppm,
    }


@app.get("/health", status_code=200)
def health() -> dict:
    """Health check endpoint."""
    state = _simulator.state.value if _simulator else "unknown"
    return {"status": "ok", "simulator_state": state}


def _require_simulator() -> None:
    if _simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialised")
