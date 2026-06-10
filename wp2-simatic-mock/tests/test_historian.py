"""Tests for historian.py -- circular buffer, per-oven state tracking, query filters."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from src.historian import Historian
from src.models import SensorReading


def _reading(
    oven_id: str = "oven-01",
    sensor_type: str = "temperature",
    value: float = 100.0,
    order_id: str | None = "ORD-2026-00001",
    ts_offset_s: int = 0,
) -> SensorReading:
    base = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=ts_offset_s)
    ts = base.strftime("%Y-%m-%dT%H:%M:%S.000Z")
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


class TestHistorianStore:
    def test_latest_returns_most_recent(self):
        h = Historian(max_readings=10)
        h.add(_reading(value=50.0, ts_offset_s=0))
        h.add(_reading(value=80.0, ts_offset_s=5))
        h.add(_reading(value=110.0, ts_offset_s=10))
        assert h.latest("oven-01", "temperature").value == 110.0

    def test_latest_returns_none_for_unknown(self):
        h = Historian()
        assert h.latest("oven-99", "temperature") is None

    def test_circular_buffer_caps_at_max(self):
        h = Historian(max_readings=3)
        for i in range(6):
            h.add(_reading(value=float(i), ts_offset_s=i))
        # Only the last 3 values should remain
        result = h.query("oven-01", "ORD-2026-00001", sensor_type="temperature")
        assert len(result) == 3
        assert [r.value for r in result] == [3.0, 4.0, 5.0]

    def test_separate_channels_independent(self):
        h = Historian(max_readings=5)
        h.add(_reading(sensor_type="temperature", value=120.0))
        h.add(_reading(sensor_type="vacuum", value=4.5))
        assert h.latest("oven-01", "temperature").value == 120.0
        assert h.latest("oven-01", "vacuum").value == 4.5

    def test_separate_ovens_independent(self):
        h = Historian()
        h.add(_reading(oven_id="oven-01", sensor_type="temperature", value=100.0))
        h.add(_reading(oven_id="oven-02", sensor_type="temperature", value=50.0))
        assert h.latest("oven-01", "temperature").value == 100.0
        assert h.latest("oven-02", "temperature").value == 50.0


class TestCycleTracking:
    def test_get_active_order_none_before_first_reading(self):
        h = Historian()
        assert h.get_active_order("oven-01") is None

    def test_active_order_set_on_first_reading_with_order(self):
        h = Historian()
        h.add(_reading(order_id="ORD-2026-00001"))
        assert h.get_active_order("oven-01") == "ORD-2026-00001"

    def test_active_order_cleared_when_order_id_becomes_null(self):
        h = Historian()
        h.add(_reading(order_id="ORD-2026-00001"))
        h.add(_reading(order_id=None))
        assert h.get_active_order("oven-01") is None

    def test_cycle_elapsed_minutes_none_when_idle(self):
        h = Historian()
        h.add(_reading(order_id=None))
        assert h.cycle_elapsed_minutes("oven-01") is None

    def test_cycle_elapsed_minutes_increases(self):
        h = Historian()
        h.add(_reading(order_id="ORD-2026-00001"))
        time.sleep(0.05)
        elapsed = h.cycle_elapsed_minutes("oven-01")
        assert elapsed is not None
        assert elapsed >= 0.0

    def test_known_ovens_populated(self):
        h = Historian()
        h.add(_reading(oven_id="oven-01"))
        h.add(_reading(oven_id="oven-02"))
        assert set(h.known_ovens()) == {"oven-01", "oven-02"}


class TestHistorianQuery:
    def _populate(self, h: Historian) -> None:
        for i in range(10):
            h.add(_reading(sensor_type="temperature", value=float(i * 10), ts_offset_s=i * 5))
        for i in range(5):
            h.add(_reading(sensor_type="moisture", value=float(2000 - i * 100), ts_offset_s=i * 5))

    def test_query_returns_all_for_order(self):
        h = Historian(max_readings=20)
        self._populate(h)
        result = h.query("oven-01", "ORD-2026-00001")
        assert len(result) == 15  # 10 temp + 5 moisture

    def test_query_filters_by_sensor_type(self):
        h = Historian(max_readings=20)
        self._populate(h)
        result = h.query("oven-01", "ORD-2026-00001", sensor_type="moisture")
        assert all(r.sensor_type == "moisture" for r in result)
        assert len(result) == 5

    def test_query_filters_by_time_range(self):
        h = Historian(max_readings=20)
        self._populate(h)
        from_ts = "2026-06-01T08:00:20.000Z"  # offset 20s = 4th reading onwards
        result = h.query("oven-01", "ORD-2026-00001", sensor_type="temperature", from_ts=from_ts)
        assert all(r.timestamp_opc >= from_ts for r in result)

    def test_query_respects_limit(self):
        h = Historian(max_readings=20)
        self._populate(h)
        result = h.query("oven-01", "ORD-2026-00001", limit=3)
        assert len(result) == 3

    def test_query_excludes_different_order(self):
        h = Historian(max_readings=20)
        self._populate(h)
        result = h.query("oven-01", "ORD-2026-00099")
        assert result == []

    def test_query_sorted_by_timestamp(self):
        h = Historian(max_readings=20)
        self._populate(h)
        result = h.query("oven-01", "ORD-2026-00001", sensor_type="temperature")
        timestamps = [r.timestamp_opc for r in result]
        assert timestamps == sorted(timestamps)
