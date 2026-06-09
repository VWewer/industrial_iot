"""Derives oven status from historian readings per C2 contract rules."""
from __future__ import annotations

from .historian import Historian


def derive_status(
    historian: Historian,
    oven_id: str,
    moisture_threshold: float,
    max_cycle_minutes: float,
) -> str:
    """Return C2 status string for the given oven.

    Rules (in priority order):
    1. idle       -- no active order
    2. timeout    -- cycle elapsed > max_cycle_minutes
    3. cycle_complete -- latest moisture < moisture_threshold
    4. running    -- order active, conditions not yet met
    """
    active_order = historian.get_active_order(oven_id)
    if active_order is None:
        return "idle"

    elapsed = historian.cycle_elapsed_minutes(oven_id)
    if elapsed is not None and elapsed >= max_cycle_minutes:
        return "timeout"

    moisture = historian.latest(oven_id, "moisture")
    if moisture is not None and moisture.value < moisture_threshold:
        return "cycle_complete"

    return "running"


def moisture_threshold_met(
    historian: Historian,
    oven_id: str,
    moisture_threshold: float,
) -> bool | None:
    """True if latest moisture reading is below threshold, None if no reading yet."""
    moisture = historian.latest(oven_id, "moisture")
    if moisture is None:
        return None
    return moisture.value < moisture_threshold
