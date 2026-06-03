"""Domain models for WP1: sensor readings and cycle state."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CycleState(str, Enum):
    IDLE = "idle"
    WARMING = "warming"
    DRYING = "drying"
    COMPLETE = "complete"


class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    VACUUM = "vacuum"
    MOISTURE = "moisture"


SENSOR_UNIT: dict[SensorType, str] = {
    SensorType.TEMPERATURE: "degC",
    SensorType.VACUUM: "mbar",
    SensorType.MOISTURE: "ppm",
}


@dataclass
class SensorReading:
    """C1 contract payload — one published MQTT message."""

    reading_id: str
    timestamp_opc: str       # ISO 8601 UTC — machine clock
    timestamp_mqtt: str      # ISO 8601 UTC — publish time
    plant: str
    oven_id: str
    sensor_type: str         # SensorType enum value
    value: float
    unit: str
    quality: str             # "Good" | "Bad" | "Uncertain"
    order_id: Optional[str]

    def to_dict(self) -> dict:
        return {
            "reading_id": self.reading_id,
            "timestamp_opc": self.timestamp_opc,
            "timestamp_mqtt": self.timestamp_mqtt,
            "plant": self.plant,
            "oven_id": self.oven_id,
            "sensor_type": self.sensor_type,
            "value": round(self.value, 3),
            "unit": self.unit,
            "quality": self.quality,
            "order_id": self.order_id,
        }


@dataclass
class CycleConfig:
    """Runtime parameters for one drying cycle."""

    order_id: str
    oven_id: str
    target_temperature_degC: float = 120.0
    target_vacuum_mbar: float = 5.0
    target_moisture_ppm: float = 300.0
    standard_cycle_minutes: float = 480.0
    warming_duration_minutes: float = 60.0


@dataclass
class SimulatorStatus:
    """Snapshot returned by GET /control/status."""

    state: str
    order_id: Optional[str]
    simulated_elapsed_minutes: float
    temperature_degC: Optional[float]
    vacuum_mbar: Optional[float]
    moisture_ppm: Optional[float]
