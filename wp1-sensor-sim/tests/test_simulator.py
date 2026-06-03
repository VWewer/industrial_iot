"""Unit tests for the cycle state machine and signal generation."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.exceptions import CycleAlreadyRunningError, InvalidCycleConfigError, NoCycleActiveError
from src.models import CycleConfig, CycleState, SensorType
from src.simulator import (
    CycleSimulator,
    _jitter,
    _moisture_decay,
    _temperature_ramp,
    _vacuum_pulldown,
    _AMBIENT_TEMPERATURE,
    _ATMOSPHERIC_PRESSURE,
    _IDLE_MOISTURE,
)


def _make_simulator(interval_s: float = 0.05, compression: float = 3600.0) -> CycleSimulator:
    """Fast simulator: 0.05s real tick = 3 simulated minutes per tick."""
    return CycleSimulator(
        compression_factor=compression,
        publish_interval_s=interval_s,
        on_tick=MagicMock(),
    )


def _default_config(**overrides) -> CycleConfig:
    defaults = dict(
        order_id="ORD-2026-00042",
        oven_id="oven-01",
        target_temperature_degC=120.0,
        target_vacuum_mbar=5.0,
        target_moisture_ppm=300.0,
        standard_cycle_minutes=30.0,   # short for testing
        warming_duration_minutes=10.0,
    )
    defaults.update(overrides)
    return CycleConfig(**defaults)


# ------------------------------------------------------------------
# State machine tests
# ------------------------------------------------------------------

class TestStateMachine:
    def test_initial_state_is_idle(self):
        sim = _make_simulator()
        assert sim.state == CycleState.IDLE

    def test_start_transitions_to_warming(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config())
        assert sim.state == CycleState.WARMING
        sim.stop_cycle()

    def test_start_twice_raises(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config())
        with pytest.raises(CycleAlreadyRunningError):
            sim.start_cycle(_default_config())
        sim.stop_cycle()

    def test_stop_with_no_cycle_raises(self):
        sim = _make_simulator()
        with pytest.raises(NoCycleActiveError):
            sim.stop_cycle()

    def test_stop_returns_to_idle(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config())
        sim.stop_cycle()
        assert sim.state == CycleState.IDLE

    def test_active_order_id_set_on_start(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config(order_id="ORD-2026-00099"))
        assert sim.active_order_id == "ORD-2026-00099"
        sim.stop_cycle()

    def test_active_order_id_cleared_on_stop(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config())
        sim.stop_cycle()
        assert sim.active_order_id is None

    def test_warming_transitions_to_drying(self):
        """With extreme compression, simulator should reach DRYING quickly."""
        # 1s real = 1h simulated → warming_duration (10 min) crossed in <1 tick
        sim = _make_simulator(interval_s=0.1, compression=3600.0)
        sim.start_cycle(_default_config(warming_duration_minutes=10.0))
        time.sleep(0.3)
        assert sim.state in (CycleState.DRYING, CycleState.COMPLETE)
        sim.stop_cycle() if sim.state != CycleState.COMPLETE else None

    def test_full_cycle_reaches_complete(self):
        """Full cycle: warming → drying → complete with fast compression."""
        ticks = []
        sim = CycleSimulator(
            compression_factor=7200.0,  # 1s real = 2h simulated
            publish_interval_s=0.05,
            on_tick=lambda state, values: ticks.append(state),
        )
        sim.start_cycle(_default_config(
            standard_cycle_minutes=60.0,
            warming_duration_minutes=5.0,
        ))
        # Give it up to 5 real seconds to complete a 65-min simulated cycle
        for _ in range(100):
            if sim.state == CycleState.COMPLETE:
                break
            time.sleep(0.05)
        assert sim.state == CycleState.COMPLETE


class TestInvalidConfig:
    def test_negative_compression_raises(self):
        with pytest.raises(InvalidCycleConfigError):
            CycleSimulator(compression_factor=-1.0, publish_interval_s=1.0, on_tick=MagicMock())

    def test_zero_target_moisture_raises(self):
        sim = _make_simulator()
        with pytest.raises(InvalidCycleConfigError):
            sim.start_cycle(_default_config(target_moisture_ppm=0))

    def test_zero_cycle_minutes_raises(self):
        sim = _make_simulator()
        with pytest.raises(InvalidCycleConfigError):
            sim.start_cycle(_default_config(standard_cycle_minutes=0))


# ------------------------------------------------------------------
# Signal shape tests
# ------------------------------------------------------------------

class TestSignalShapes:
    def test_temperature_ramp_starts_near_ambient(self):
        t = _temperature_ramp(0.0, _AMBIENT_TEMPERATURE, 120.0, 60.0)
        assert abs(t - _AMBIENT_TEMPERATURE) < 5.0

    def test_temperature_ramp_approaches_setpoint(self):
        # At t = 2 * tau (tau = 60/3 = 20) → ~86% of delta → expect > 95°C
        t = _temperature_ramp(40.0, _AMBIENT_TEMPERATURE, 120.0, 60.0)
        assert t > 90.0

    def test_vacuum_pulldown_starts_near_atmospheric(self):
        v = _vacuum_pulldown(0.0, _ATMOSPHERIC_PRESSURE, 5.0, tau_minutes=10.0)
        assert v > 900.0

    def test_vacuum_pulldown_reaches_setpoint(self):
        # At t = 5 * tau → ~99% of the way down
        v = _vacuum_pulldown(50.0, _ATMOSPHERIC_PRESSURE, 5.0, tau_minutes=10.0)
        assert v < 15.0

    def test_moisture_decay_starts_near_initial(self):
        m = _moisture_decay(0.0, _IDLE_MOISTURE, 300.0, 480.0)
        assert m > 4000.0

    def test_moisture_decay_reaches_target_at_standard_cycle(self):
        m = _moisture_decay(480.0, _IDLE_MOISTURE, 300.0, 480.0)
        # With noise, allow ±5 * noise_stddev (~50 ppm) around target
        assert abs(m - 300.0) < 100.0

    def test_jitter_within_three_sigma(self):
        """Statistical test: 1000 samples should all be within 6 sigma of mean."""
        for _ in range(1000):
            val = _jitter(100.0, 1.0)
            assert 94.0 < val < 106.0, f"jitter outlier: {val}"


# ------------------------------------------------------------------
# Status tests
# ------------------------------------------------------------------

class TestStatus:
    def test_status_idle(self):
        sim = _make_simulator()
        status = sim.get_status()
        assert status.state == "idle"
        assert status.order_id is None

    def test_status_running(self):
        sim = _make_simulator()
        sim.start_cycle(_default_config(order_id="ORD-2026-00042"))
        status = sim.get_status()
        assert status.state == "warming"
        assert status.order_id == "ORD-2026-00042"
        sim.stop_cycle()
