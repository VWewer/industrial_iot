"""Custom exceptions for WP2 SIMATIC mock."""
from __future__ import annotations


class MQTTConnectionError(Exception):
    """Raised when the MQTT broker cannot be reached on startup."""


class OvenNotFoundError(Exception):
    """Raised when a /process-state request targets an oven with no data."""


class InvalidMessageError(Exception):
    """Raised when an inbound MQTT payload cannot be parsed as a C1 message."""
