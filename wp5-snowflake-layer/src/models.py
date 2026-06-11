from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, field_validator

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

_SENSOR_TYPES = {"temperature", "vacuum", "moisture"}
_QUALITY_VALUES = {"Good", "Bad", "Uncertain"}
_EVENT_TYPES = {
    "cycle_started",
    "cycle_confirmed",
    "cycle_aborted",
    "cycle_timeout",
    "sap_confirmation_failed",
}


class SensorReading(BaseModel):
    reading_id: str
    timestamp_opc: str
    timestamp_mqtt: str
    plant: str
    oven_id: str
    sensor_type: str
    value: float
    unit: str
    quality: str
    order_id: str | None = None

    @field_validator("sensor_type")
    @classmethod
    def sensor_type_valid(cls, v: str) -> str:
        if v not in _SENSOR_TYPES:
            raise ValueError(f"sensor_type must be one of {sorted(_SENSOR_TYPES)}")
        return v

    @field_validator("quality")
    @classmethod
    def quality_valid(cls, v: str) -> str:
        if v not in _QUALITY_VALUES:
            raise ValueError(f"quality must be one of {sorted(_QUALITY_VALUES)}")
        return v

    @field_validator("timestamp_opc", "timestamp_mqtt")
    @classmethod
    def timestamp_format(cls, v: str) -> str:
        if not ISO_RE.match(v):
            raise ValueError(f"Timestamp must be ISO 8601 UTC with Z suffix: {v!r}")
        return v


class CycleEvent(BaseModel):
    event_id: str
    event_type: str
    order_id: str
    oven_id: str
    operator_id: str | None = None
    timestamp: str
    payload: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def event_type_valid(cls, v: str) -> str:
        if v not in _EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(_EVENT_TYPES)}")
        return v

    @field_validator("timestamp")
    @classmethod
    def timestamp_format(cls, v: str) -> str:
        if not ISO_RE.match(v):
            raise ValueError(f"Timestamp must be ISO 8601 UTC with Z suffix: {v!r}")
        return v


class CycleEventResponse(BaseModel):
    status: str
    event_id: str


class GoldCycleSummary(BaseModel):
    order_id: str
    material_id: str
    material_description: str | None = None
    plant: str
    oven_id: str
    cycle_start_time: str | None = None
    cycle_end_time: str | None = None
    actual_duration_minutes: float | None = None
    standard_cycle_minutes: int | None = None
    delta_minutes: float | None = None
    peak_temperature_degC: float | None = None
    min_vacuum_mbar: float | None = None
    final_moisture_ppm: float | None = None
    target_moisture_ppm: float | None = None
    spec_met: bool | None = None
    quality_check_passed: bool | None = None
    operator_id: str | None = None
    sap_confirmation_number: str | None = None
    goods_movement_posted: bool = False


class CycleEfficiencyRow(BaseModel):
    material_id: str
    material_description: str | None = None
    total_cycles: int
    avg_actual_minutes: float | None = None
    avg_standard_minutes: float | None = None
    avg_delta_minutes: float | None = None
    cycles_faster_than_standard: int = 0
    cycles_meeting_spec: int = 0
    avg_final_moisture_ppm: float | None = None
