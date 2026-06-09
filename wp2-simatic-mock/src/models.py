"""Domain models for WP2: MQTT readings, historian state, and C2/C3 API responses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel


# --- sensor reading (C1 inbound) ---

@dataclass
class SensorReading:
    """One parsed C1 MQTT message."""

    reading_id: str
    timestamp_opc: str    # ISO 8601 UTC -- machine clock
    timestamp_mqtt: str   # ISO 8601 UTC -- publish time
    plant: str
    oven_id: str
    sensor_type: str      # temperature | vacuum | moisture
    value: float
    unit: str
    quality: str          # Good | Bad | Uncertain
    order_id: Optional[str]


# --- C2 response ---

class ProcessStateResponse(BaseModel):
    """GET /process-state/{oven_id} -- C2 contract."""

    oven_id: str
    order_id: Optional[str]
    status: str                       # idle | running | cycle_complete | timeout
    temperature_degC: Optional[float]
    vacuum_mbar: Optional[float]
    moisture_ppm: Optional[float]
    cycle_elapsed_minutes: Optional[float]
    moisture_threshold_met: Optional[bool]
    timestamp: str


# --- C3 response ---

class HistorianReadingItem(BaseModel):
    """One row in a C3 historian response."""

    reading_id: str
    timestamp_opc: str
    sensor_type: str
    value: float
    unit: str
    quality: str


class HistorianResponse(BaseModel):
    """GET /historian -- C3 contract."""

    order_id: str
    count: int
    readings: list[HistorianReadingItem]
