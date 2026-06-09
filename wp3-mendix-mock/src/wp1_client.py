"""HTTP client for WP1 control API -- triggers cycle start."""
from __future__ import annotations

import logging

import httpx

from .exceptions import WP1ClientError

log = logging.getLogger(__name__)

_TIMEOUT = 5.0


class WP1Client:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def start_cycle(self, order_id: str, oven_id: str, target_moisture_ppm: float) -> None:
        try:
            resp = httpx.post(
                f"{self._base}/control/start",
                json={
                    "order_id": order_id,
                    "oven_id": oven_id,
                    "target_moisture_ppm": target_moisture_ppm,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise WP1ClientError(f"POST /control/start failed: {exc}") from exc
        log.info(
            "WP1 cycle start triggered",
            extra={"order_id": order_id, "oven_id": oven_id},
        )
