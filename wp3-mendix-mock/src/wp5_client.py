"""HTTP client for WP5 MES events webhook -- C10 contract."""
from __future__ import annotations

import logging

import httpx

from .exceptions import WP5ClientError
from .models import CycleEvent

log = logging.getLogger(__name__)

_TIMEOUT = 5.0


class WP5Client:
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def post_event(self, event: CycleEvent) -> None:
        try:
            resp = httpx.post(self._url, json=event.to_dict(), timeout=_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise WP5ClientError(f"POST {self._url} failed: {exc}") from exc
        log.info(
            "MES event posted to WP5",
            extra={"event_type": event.event_type, "order_id": event.order_id},
        )
