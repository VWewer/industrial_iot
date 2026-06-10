"""In-memory circular historian: stores C1 readings and tracks per-oven cycle state."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from .models import SensorReading

log = logging.getLogger(__name__)


class Historian:
    """Thread-safe circular buffer keyed by (oven_id, sensor_type).

    Also tracks active order and cycle start time per oven so the API layer
    can compute cycle_elapsed_minutes without touching raw readings.
    """

    def __init__(self, max_readings: int = 500) -> None:
        self._max = max_readings
        self._buffers: dict[tuple[str, str], deque[SensorReading]] = {}
        self._active_order: dict[str, Optional[str]] = {}
        self._cycle_start: dict[str, datetime] = {}
        self._lock = Lock()

    # --- write path ---

    def add(self, reading: SensorReading) -> None:
        """Store a reading and update per-oven cycle tracking."""
        key = (reading.oven_id, reading.sensor_type)
        oven_id = reading.oven_id
        new_order = reading.order_id

        with self._lock:
            prev_order = self._active_order.get(oven_id)
            if prev_order is None and new_order is not None:
                self._cycle_start[oven_id] = datetime.now(timezone.utc)
                log.info(
                    "Cycle started on oven",
                    extra={"oven_id": oven_id, "order_id": new_order},
                )
            elif prev_order is not None and new_order is None:
                self._cycle_start.pop(oven_id, None)
                log.info(
                    "Cycle ended on oven",
                    extra={"oven_id": oven_id, "prev_order": prev_order},
                )
            self._active_order[oven_id] = new_order

            if key not in self._buffers:
                self._buffers[key] = deque(maxlen=self._max)
            self._buffers[key].append(reading)

    # --- read path ---

    def latest(self, oven_id: str, sensor_type: str) -> Optional[SensorReading]:
        """Return the most recent reading for (oven_id, sensor_type), or None."""
        key = (oven_id, sensor_type)
        with self._lock:
            buf = self._buffers.get(key)
            return buf[-1] if buf else None

    def get_active_order(self, oven_id: str) -> Optional[str]:
        with self._lock:
            return self._active_order.get(oven_id)

    def cycle_elapsed_minutes(self, oven_id: str) -> Optional[float]:
        """Elapsed minutes since the current cycle started, or None if idle."""
        with self._lock:
            start = self._cycle_start.get(oven_id)
        if start is None:
            return None
        delta = datetime.now(timezone.utc) - start
        return round(delta.total_seconds() / 60.0, 2)

    def known_ovens(self) -> list[str]:
        with self._lock:
            return list(self._active_order.keys())

    def query(
        self,
        oven_id: str,
        order_id: str,
        sensor_type: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 1000,
    ) -> list[SensorReading]:
        """Return readings matching the query filters, newest-last, up to limit rows."""
        results: list[SensorReading] = []

        with self._lock:
            for (o_id, s_type), buf in self._buffers.items():
                if o_id != oven_id:
                    continue
                if sensor_type and s_type != sensor_type:
                    continue
                for r in buf:
                    if r.order_id != order_id:
                        continue
                    if from_ts and r.timestamp_opc < from_ts:
                        continue
                    if to_ts and r.timestamp_opc > to_ts:
                        continue
                    results.append(r)

        results.sort(key=lambda r: r.timestamp_opc)
        return results[:limit]
