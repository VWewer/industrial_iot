"""Tests for status_engine.py -- all four C2 status transitions."""
from __future__ import annotations

import time
import uuid

import pytest

from src.historian import Historian
from src.models import SensorReading
from src.status_engine import derive_status, moisture_threshold_met


def _reading(
    oven_id: str = "oven-01",
    sensor_type: str = "temperature",
    value: float = 100.0,
    order_id: str | None = "ORD-2026-00001",
) -> SensorReading:
    ts = "2026-06-01T08:00:00.000Z"
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


THRESHOLD = 500.0
MAX_CYCLE = 600.0


class TestDeriveStatus:
    def test_idle_when_no_active_order(self):
        h = Historian()
        h.add(_reading(order_id=None))
        assert derive_status(h, "oven-01", THRESHOLD, MAX_CYCLE) == "idle"

    def test_idle_for_unknown_oven(self):
        h = Historian()
        assert derive_status(h, "oven-99", THRESHOLD, MAX_CYCLE) == "idle"

    def test_running_when_order_active_and_moisture_high(self):
        h = Historian()
        h.add(_reading(sensor_type="temperature", value=120.0))
        h.add(_reading(sensor_type="moisture", value=2000.0))
        assert derive_status(h, "oven-01", THRESHOLD, MAX_CYCLE) == "running"

    def test_cycle_complete_when_moisture_below_threshold(self):
        h = Historian()
        h.add(_reading(sensor_type="temperature", value=120.0))
        h.add(_reading(sensor_type="moisture", value=250.0))  # below 500 threshold
        assert derive_status(h, "oven-01", THRESHOLD, MAX_CYCLE) == "cycle_complete"

    def test_cycle_complete_exactly_at_threshold_is_not_complete(self):
        h = Historian()
        h.add(_reading(sensor_type="moisture", value=500.0))  # equal, not below
        assert derive_status(h, "oven-01", THRESHOLD, MAX_CYCLE) == "running"

    def test_running_when_no_moisture_reading_yet(self):
        # No moisture data yet -- cannot infer cycle_complete
        h = Historian()
        h.add(_reading(sensor_type="temperature", value=120.0))
        assert derive_status(h, "oven-01", THRESHOLD, MAX_CYCLE) == "running"

    def test_timeout_when_elapsed_exceeds_max(self):
        # Simulate elapsed > max by setting max_cycle to near-zero
        h = Historian()
        h.add(_reading(sensor_type="moisture", value=2000.0))
        time.sleep(0.05)
        tiny_max = 0.0  # 0 minutes -- will always timeout
        assert derive_status(h, "oven-01", THRESHOLD, tiny_max) == "timeout"

    def test_timeout_takes_priority_over_cycle_complete(self):
        h = Historian()
        h.add(_reading(sensor_type="moisture", value=100.0))  # would be cycle_complete
        time.sleep(0.05)
        tiny_max = 0.0
        # timeout should win
        assert derive_status(h, "oven-01", THRESHOLD, tiny_max) == "timeout"


class TestMoistureThresholdMet:
    def test_none_when_no_moisture_reading(self):
        h = Historian()
        assert moisture_threshold_met(h, "oven-01", THRESHOLD) is None

    def test_true_when_below_threshold(self):
        h = Historian()
        h.add(_reading(sensor_type="moisture", value=200.0))
        assert moisture_threshold_met(h, "oven-01", THRESHOLD) is True

    def test_false_when_above_threshold(self):
        h = Historian()
        h.add(_reading(sensor_type="moisture", value=900.0))
        assert moisture_threshold_met(h, "oven-01", THRESHOLD) is False
