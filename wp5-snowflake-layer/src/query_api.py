from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from .snowflake_client import _svc

log = logging.getLogger(__name__)

router = APIRouter()


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        key = k.lower()
        if hasattr(v, "isoformat"):
            formatted = v.isoformat()
            if hasattr(v, "tzinfo") and v.tzinfo is not None:
                formatted = formatted.replace("+00:00", "Z")
            out[key] = formatted
        else:
            out[key] = v
    return out


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "wp5-snowflake-layer",
        "snowflake_connected": _svc().is_connected(),
    }


@router.get("/gold/cycles")
def list_cycles() -> list:
    rows = _svc().fetchall("SELECT * FROM v_recent_cycles")
    return [_row_to_dict(r) for r in rows]


@router.get("/gold/cycles/{order_id}")
def get_cycle(order_id: str) -> dict:
    row = _svc().fetchone(
        "SELECT * FROM gold_cycle_summary WHERE order_id = %s", (order_id,)
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Cycle not found: {order_id}")
    result = _row_to_dict(row)
    readings = _svc().fetchall(
        "SELECT * FROM silver_sensor_readings WHERE order_id = %s ORDER BY timestamp_opc",
        (order_id,),
    )
    result["sensor_readings"] = [_row_to_dict(r) for r in readings]
    return result


@router.get("/gold/efficiency")
def list_efficiency() -> list:
    rows = _svc().fetchall("SELECT * FROM v_cycle_efficiency")
    return [_row_to_dict(r) for r in rows]
