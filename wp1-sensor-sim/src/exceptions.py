"""Custom exceptions for WP1 sensor simulator."""
from __future__ import annotations


class SimulatorError(Exception):
    """Base exception for simulator failures."""


class CycleAlreadyRunningError(SimulatorError):
    """Raised when start is called while a cycle is already active."""


class NoCycleActiveError(SimulatorError):
    """Raised when stop is called with no active cycle."""


class MQTTConnectionError(SimulatorError):
    """Raised when the MQTT broker cannot be reached."""


class InvalidCycleConfigError(SimulatorError):
    """Raised when CycleConfig contains invalid values."""
