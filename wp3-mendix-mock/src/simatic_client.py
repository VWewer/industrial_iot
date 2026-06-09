"""HTTP client for WP2 SIMATIC mock -- C2 contract."""
from __future__ import annotations

import logging

import httpx

from .exceptions import SimaticClientError

log = logging.getLogger(__name__)

_TIMEOUT = 5.0


class SimaticClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def get_process_state(self, oven_id: str) -> dict:
        try:
            resp = httpx.get(
                f"{self._base}/process-state/{oven_id}",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SimaticClientError(
                f"GET /process-state/{oven_id} failed: {exc}"
            ) from exc
        return resp.json()
