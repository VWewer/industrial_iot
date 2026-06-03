"""Cycle state machine and sensor signal generation for WP1."""
from __future__ import annotations

import logging
import math
import random
import threading
import time
from typing import Callable, Optional

from .exceptions import CycleAlreadyRunningError, InvalidCycleConfigError, NoCycleActiveError
from .models import CycleConfig, CycleState, SensorType, SimulatorStatus

log = logging.getLogger(__name__)

# Gaussian noise standard deviations per sensor type
_NOISE_STDDEV: dict[SensorType, float] = {
    SensorType.TEMPERATURE: 0.5,   # +/-0.5 degC jitter
    SensorType.VACUUM: 0.05,       # +/-0.05 mbar jitter
    SensorType.MOISTURE: 10.0,     # +/-10 ppm jitter
}

# Ambient / atmospheric baseline values
_AMBIENT_TEMPERATURE = 25.0
_ATMOSPHERIC_PRESSURE = 1013.0
_IDLE_MOISTURE = 5000.0


class CycleSimulator:
    """Runs the drying cycle state machine and generates physically plausible sensor values.

    Time is tracked as simulated minutes. Real elapsed time is scaled by
    compression_factor so a 60x-compressed cycle runs in 1/60th real time.
    """

    def __init__(
        self,
        compression_factor: float,
        publish_interval_s: float,
        on_tick: Callable[[CycleState, dict[SensorType, float]], None],
    ) -> None:
        if compression_factor <= 0:
            raise InvalidCycleConfigError(f"compression_factor must be > 0, got {compression_factor}")
        self._compression = compression_factor
        self._publish_interval_s = publish_interval_s
        self._on_tick = on_tick

        self._state = CycleState.IDLE
        self._config: Optional[CycleConfig] = None
        self._simulated_elapsed_min: float = 0.0
        self._last_values: dict[SensorType, float] = {
            SensorType.TEMPERATURE: _AMBIENT_TEMPERATURE,
            SensorType.VACUUM: _ATMOSPHERIC_PRESSURE,
            SensorType.MOISTURE: _IDLE_MOISTURE,
        }

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public control interface
    # ------------------------------------------------------------------

    def start_cycle(self, config: CycleConfig) -> None:
        """Transition from IDLE to WARMING and begin the simulation loop."""
        with self._lock:
            if self._state != CycleState.IDLE:
                raise CycleAlreadyRunningError(
                    f"Cannot start: current state is {self._state.value}"
                )
            if config.target_moisture_ppm <= 0 or config.standard_cycle_minutes <= 0:
                raise InvalidCycleConfigError("target_moisture_ppm and standard_cycle_minutes must be > 0")

            self._config = config
            self._simulated_elapsed_min = 0.0
            self._state = CycleState.WARMING
            self._stop_event.clear()

        log.info(
            "Cycle started",
            extra={"order_id": config.order_id, "oven_id": config.oven_id, "state": "warming"},
        )
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator-loop")
        self._thread.start()

    def stop_cycle(self) -> None:
        """Force-stop the simulation and return to IDLE."""
        with self._lock:
            if self._state == CycleState.IDLE:
                raise NoCycleActiveError("Cannot stop: no active cycle")
            self._stop_event.set()
            self._state = CycleState.IDLE
            self._config = None
            self._simulated_elapsed_min = 0.0

        log.info("Cycle force-stopped")

    def get_status(self) -> SimulatorStatus:
        with self._lock:
            order_id = self._config.order_id if self._config else None
            return SimulatorStatus(
                state=self._state.value,
                order_id=order_id,
                simulated_elapsed_minutes=round(self._simulated_elapsed_min, 2),
                temperature_degC=round(self._last_values[SensorType.TEMPERATURE], 3),
                vacuum_mbar=round(self._last_values[SensorType.VACUUM], 3),
                moisture_ppm=round(self._last_values[SensorType.MOISTURE], 3),
            )

    @property
    def state(self) -> CycleState:
        return self._state

    @property
    def active_order_id(self) -> Optional[str]:
        return self._config.order_id if self._config else None

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main loop: tick every publish_interval_s real seconds."""
        # Simulated minutes advanced per real-second tick
        sim_minutes_per_tick = (self._publish_interval_s * self._compression) / 60.0

        while not self._stop_event.is_set():
            time.sleep(self._publish_interval_s)

            with self._lock:
                if self._stop_event.is_set():
                    break
                self._simulated_elapsed_min += sim_minutes_per_tick
                self._advance_state()
                values = self._compute_values()
                self._last_values = values
                current_state = self._state

            self._on_tick(current_state, values)

            if current_state == CycleState.COMPLETE:
                log.info(
                    "Cycle complete -- moisture threshold met",
                    extra={"order_id": self.active_order_id},
                )
                break

    def _advance_state(self) -> None:
        """Check whether state transitions are due -- must be called under lock."""
        config = self._config
        if config is None:
            return

        if self._state == CycleState.WARMING:
            if self._simulated_elapsed_min >= config.warming_duration_minutes:
                self._state = CycleState.DRYING
                log.info("State transition: WARMING -> DRYING", extra={"order_id": config.order_id})

        elif self._state == CycleState.DRYING:
            moisture = self._last_values[SensorType.MOISTURE]
            if moisture <= config.target_moisture_ppm:
                self._state = CycleState.COMPLETE
                log.info(
                    "State transition: DRYING -> COMPLETE",
                    extra={"order_id": config.order_id, "moisture_ppm": moisture},
                )

    def _compute_values(self) -> dict[SensorType, float]:
        """Generate sensor values for the current simulated elapsed time."""
        config = self._config
        if config is None or self._state == CycleState.IDLE:
            return {
                SensorType.TEMPERATURE: _jitter(_AMBIENT_TEMPERATURE, _NOISE_STDDEV[SensorType.TEMPERATURE]),
                SensorType.VACUUM: _jitter(_ATMOSPHERIC_PRESSURE, _NOISE_STDDEV[SensorType.VACUUM]),
                SensorType.MOISTURE: _jitter(_IDLE_MOISTURE, _NOISE_STDDEV[SensorType.MOISTURE]),
            }

        t = self._simulated_elapsed_min

        if self._state == CycleState.WARMING:
            temperature = _temperature_ramp(
                t,
                _AMBIENT_TEMPERATURE,
                config.target_temperature_degC,
                config.warming_duration_minutes,
            )
            # Vacuum pumps not yet engaged during warming
            vacuum = _jitter(_ATMOSPHERIC_PRESSURE, _NOISE_STDDEV[SensorType.VACUUM])
            moisture = _jitter(_IDLE_MOISTURE, _NOISE_STDDEV[SensorType.MOISTURE])

        elif self._state in (CycleState.DRYING, CycleState.COMPLETE):
            drying_t = t - config.warming_duration_minutes  # time since drying started

            temperature = _jitter(config.target_temperature_degC, _NOISE_STDDEV[SensorType.TEMPERATURE])

            vacuum = _vacuum_pulldown(
                drying_t,
                _ATMOSPHERIC_PRESSURE,
                config.target_vacuum_mbar,
                tau_minutes=10.0,
            )

            moisture = _moisture_decay(
                drying_t,
                initial_ppm=_IDLE_MOISTURE,
                target_ppm=config.target_moisture_ppm,
                standard_cycle_minutes=config.standard_cycle_minutes,
            )
            # Clamp: moisture cannot go below zero
            moisture = max(moisture, 0.0)
        else:
            temperature = _jitter(_AMBIENT_TEMPERATURE, _NOISE_STDDEV[SensorType.TEMPERATURE])
            vacuum = _jitter(_ATMOSPHERIC_PRESSURE, _NOISE_STDDEV[SensorType.VACUUM])
            moisture = _jitter(_IDLE_MOISTURE, _NOISE_STDDEV[SensorType.MOISTURE])

        return {
            SensorType.TEMPERATURE: temperature,
            SensorType.VACUUM: vacuum,
            SensorType.MOISTURE: moisture,
        }


# ------------------------------------------------------------------
# Signal shape functions
# ------------------------------------------------------------------

def _jitter(value: float, stddev: float) -> float:
    """Add Gaussian noise to a value."""
    return value + random.gauss(0.0, stddev)


def _temperature_ramp(
    t: float,
    t_ambient: float,
    t_setpoint: float,
    warming_duration: float,
) -> float:
    """Exponential approach from ambient to setpoint over warming_duration minutes."""
    # tau chosen so 95% of setpoint is reached at warming_duration
    tau = warming_duration / 3.0
    base = t_ambient + (t_setpoint - t_ambient) * (1.0 - math.exp(-t / tau))
    return _jitter(base, _NOISE_STDDEV[SensorType.TEMPERATURE])


def _vacuum_pulldown(
    drying_t: float,
    atmospheric: float,
    target_vacuum: float,
    tau_minutes: float,
) -> float:
    """Exponential pressure drop from atmospheric to target vacuum after pumps engage."""
    base = target_vacuum + (atmospheric - target_vacuum) * math.exp(-drying_t / tau_minutes)
    return max(_jitter(base, _NOISE_STDDEV[SensorType.VACUUM]), 0.1)


def _moisture_decay(
    drying_t: float,
    initial_ppm: float,
    target_ppm: float,
    standard_cycle_minutes: float,
) -> float:
    """Exponential moisture decay calibrated to reach target at standard_cycle_minutes."""
    # k chosen so M(standard_cycle_minutes) == target_ppm
    k = -math.log(target_ppm / initial_ppm) / standard_cycle_minutes
    base = initial_ppm * math.exp(-k * drying_t)
    return _jitter(base, _NOISE_STDDEV[SensorType.MOISTURE])
