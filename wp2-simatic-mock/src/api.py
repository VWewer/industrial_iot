"""FastAPI application exposing C2 (process state) and C3 (historian query) endpoints."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from .exceptions import OvenNotFoundError
from .historian import Historian
from .models import (
    HistorianReadingItem,
    HistorianResponse,
    ProcessStateResponse,
)
from .status_engine import derive_status, moisture_threshold_met

log = logging.getLogger(__name__)

app = FastAPI(title="WP2 SIMATIC Mock", version="1.0.0")

_historian: Optional[Historian] = None
_moisture_threshold: float = 500.0
_max_cycle_minutes: float = 600.0


def init_app(historian: Historian, moisture_threshold: float, max_cycle_minutes: float) -> None:
    global _historian, _moisture_threshold, _max_cycle_minutes
    _historian = historian
    _moisture_threshold = moisture_threshold
    _max_cycle_minutes = max_cycle_minutes


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _get_historian() -> Historian:
    if _historian is None:
        raise RuntimeError("Historian not initialised -- call init_app() first")
    return _historian


# --- endpoints ---

@app.get("/health")
def health() -> dict:
    h = _get_historian()
    return {
        "status": "ok",
        "service": "wp2-simatic-mock",
        "known_ovens": h.known_ovens(),
    }


@app.get("/process-state/{oven_id}", response_model=ProcessStateResponse)
def process_state(oven_id: str) -> ProcessStateResponse:
    """C2 -- current oven status and latest sensor readings."""
    h = _get_historian()

    temp = h.latest(oven_id, "temperature")
    vacuum = h.latest(oven_id, "vacuum")
    moisture = h.latest(oven_id, "moisture")

    # Return idle state even for unknown ovens (no data yet)
    active_order = h.get_active_order(oven_id)
    status = derive_status(h, oven_id, _moisture_threshold, _max_cycle_minutes)
    elapsed = h.cycle_elapsed_minutes(oven_id)
    threshold_met = moisture_threshold_met(h, oven_id, _moisture_threshold)

    log.info(
        "Process state requested",
        extra={"oven_id": oven_id, "status": status, "order_id": active_order},
    )

    return ProcessStateResponse(
        oven_id=oven_id,
        order_id=active_order,
        status=status,
        temperature_degC=round(temp.value, 2) if temp else None,
        vacuum_mbar=round(vacuum.value, 2) if vacuum else None,
        moisture_ppm=round(moisture.value, 2) if moisture else None,
        cycle_elapsed_minutes=elapsed,
        moisture_threshold_met=threshold_met,
        timestamp=_utc_now(),
    )


@app.get("/historian", response_model=HistorianResponse)
def historian_query(
    order_id: str = Query(..., description="Production order to filter by"),
    sensor_type: Optional[str] = Query(None, description="temperature | vacuum | moisture"),
    oven_id: str = Query("oven-01", description="Oven identifier"),
    from_ts: Optional[str] = Query(None, alias="from", description="ISO 8601 start timestamp"),
    to_ts: Optional[str] = Query(None, alias="to", description="ISO 8601 end timestamp"),
    limit: int = Query(1000, ge=1, le=10000),
) -> HistorianResponse:
    """C3 -- time-series query over buffered readings."""
    h = _get_historian()
    readings = h.query(
        oven_id=oven_id,
        order_id=order_id,
        sensor_type=sensor_type,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )

    log.info(
        "Historian query",
        extra={"order_id": order_id, "count": len(readings), "oven_id": oven_id},
    )

    return HistorianResponse(
        order_id=order_id,
        count=len(readings),
        readings=[
            HistorianReadingItem(
                reading_id=r.reading_id,
                timestamp_opc=r.timestamp_opc,
                sensor_type=r.sensor_type,
                value=r.value,
                unit=r.unit,
                quality=r.quality,
            )
            for r in readings
        ],
    )
