from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from ..exceptions import SnowflakeQueryError
from ..models import CycleEvent, CycleEventResponse
from ..snowflake_client import _svc

log = logging.getLogger(__name__)

router = APIRouter()

_INSERT_SQL = """
INSERT INTO bronze_mes_events (
    event_id, event_type, raw_payload, order_id, oven_id, operator_id, event_time, payload_json
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


@router.post("/events", response_model=CycleEventResponse)
def receive_event(event: CycleEvent) -> CycleEventResponse:
    raw = json.dumps(event.model_dump())
    payload_str = json.dumps(event.payload) if event.payload else None
    try:
        _svc().execute_many(
            _INSERT_SQL,
            [
                (
                    event.event_id,
                    event.event_type,
                    raw,
                    event.order_id,
                    event.oven_id,
                    event.operator_id,
                    event.timestamp,
                    payload_str,
                )
            ],
        )
    except SnowflakeQueryError as exc:
        log.error(
            "Failed to insert MES event: %s",
            exc,
            extra={"event_id": event.event_id},
        )
        raise HTTPException(status_code=503, detail="Failed to store event")
    log.info(
        "MES event ingested",
        extra={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "order_id": event.order_id,
        },
    )
    return CycleEventResponse(status="accepted", event_id=event.event_id)
