"""HTTP client for WP4 SAP mock -- C5, C6, C7, C8 contracts."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .exceptions import SAPClientError
from .models import GoodsMovementRequest, MaterialSpec, SAPConfirmationRequest

log = logging.getLogger(__name__)

_TIMEOUT = 10.0


def _check(resp: httpx.Response, context: str) -> None:
    """Raise SAPClientError on any non-2xx status without requiring a request object."""
    if not resp.is_success:
        raise SAPClientError(f"{context} returned {resp.status_code}")


class SAPClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    # --- C6: production orders ---

    def get_orders(self, status: Optional[str] = None, plant: Optional[str] = None) -> list[dict]:
        params: dict = {}
        if status:
            params["status"] = status
        if plant:
            params["plant"] = plant
        try:
            resp = httpx.get(
                f"{self._base}/odata/v1/ProductionOrders",
                params=params,
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise SAPClientError(f"GET ProductionOrders failed: {exc}") from exc
        _check(resp, "GET ProductionOrders")
        data = resp.json()
        return data.get("value", [])

    def get_order(self, order_id: str) -> dict:
        try:
            resp = httpx.get(
                f"{self._base}/odata/v1/ProductionOrders('{order_id}')",
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise SAPClientError(f"GET ProductionOrders('{order_id}') failed: {exc}") from exc
        _check(resp, f"GET ProductionOrders('{order_id}')")
        return resp.json()

    # --- C7: material master ---

    def get_material(self, material_id: str) -> MaterialSpec:
        try:
            resp = httpx.get(
                f"{self._base}/odata/v1/Materials('{material_id}')",
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise SAPClientError(f"GET Materials('{material_id}') failed: {exc}") from exc
        _check(resp, f"GET Materials('{material_id}')")
        d = resp.json()
        return MaterialSpec(
            material_id=d["material_id"],
            material_description=d["material_description"],
            target_moisture_ppm=int(d["target_moisture_ppm"]),
            target_temperature_degC=float(d["target_temperature_degC"]),
            target_vacuum_mbar=float(d["target_vacuum_mbar"]),
            standard_cycle_minutes=int(d["standard_cycle_minutes"]),
            max_cycle_minutes=int(d["max_cycle_minutes"]),
            weight_kg=float(d["weight_kg"]),
        )

    # --- C5: operation confirmation ---

    def post_confirmation(self, req: SAPConfirmationRequest) -> dict:
        try:
            resp = httpx.post(
                f"{self._base}/odata/v1/OperationConfirmations",
                json=req.to_dict(),
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise SAPClientError(f"POST OperationConfirmations failed: {exc}") from exc
        _check(resp, "POST OperationConfirmations")
        log.info("SAP confirmation posted", extra={"order_id": req.order_id})
        return resp.json()

    # --- C8: goods receipt ---

    def post_goods_movement(self, req: GoodsMovementRequest) -> dict:
        try:
            resp = httpx.post(
                f"{self._base}/odata/v1/GoodsMovements",
                json=req.to_dict(),
                timeout=_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise SAPClientError(f"POST GoodsMovements failed: {exc}") from exc
        _check(resp, "POST GoodsMovements")
        log.info("Goods movement posted", extra={"order_id": req.order_id})
        return resp.json()
