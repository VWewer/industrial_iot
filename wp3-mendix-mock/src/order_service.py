"""Order state machine and in-memory store for WP3."""
from __future__ import annotations

import logging
import threading
from typing import Optional

from .exceptions import InvalidStateTransitionError, OrderNotFoundError
from .models import Order

log = logging.getLogger(__name__)


class OrderService:
    """Thread-safe in-memory store for order state, keyed by order_id."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._lock = threading.Lock()

    # --- read ---

    def get(self, order_id: str) -> Order:
        with self._lock:
            order = self._orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order '{order_id}' not found in local store")
        return order

    def list_by_status(self, status: str) -> list[Order]:
        with self._lock:
            return [o for o in self._orders.values() if o.status == status]

    def all_orders(self) -> list[Order]:
        with self._lock:
            return list(self._orders.values())

    # --- write ---

    def upsert_from_sap(self, sap_data: dict) -> Order:
        """Insert or refresh an order from a SAP C6 payload. Preserves local status if present."""
        order_id = sap_data["order_id"]
        with self._lock:
            existing = self._orders.get(order_id)
            if existing is not None:
                return existing
            order = Order(
                order_id=order_id,
                material_id=sap_data["material_id"],
                plant=sap_data["plant"],
                oven_id=sap_data["oven_id"],
                status="released",
            )
            self._orders[order_id] = order
            log.info(
                "Order created from SAP",
                extra={"order_id": order_id, "material_id": order.material_id},
            )
        return order

    def start(
        self,
        order_id: str,
        operator_id: str,
        actual_start: str,
        target_moisture_ppm: Optional[float] = None,
    ) -> Order:
        """Transition: released -> in-progress. All field assignments are atomic with the status change."""
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise OrderNotFoundError(f"Order '{order_id}' not found in local store")
            if order.status != "released":
                raise InvalidStateTransitionError(
                    order_id=order_id,
                    current=order.status,
                    attempted="in-progress",
                )
            order.status = "in-progress"
            order.operator_id = operator_id
            order.actual_start = actual_start
            if target_moisture_ppm is not None:
                order.target_moisture_ppm = target_moisture_ppm
        log.info(
            "Order started",
            extra={"order_id": order_id, "operator_id": operator_id},
        )
        return order

    def confirm(
        self,
        order_id: str,
        quality_check_passed: bool,
        final_moisture_ppm: float,
        actual_end: str,
        cycle_confirmed_at: str,
    ) -> Order:
        """Transition: in-progress -> confirmed."""
        order = self._transition(order_id, "in-progress", "confirmed")
        order.quality_check_passed = quality_check_passed
        order.final_moisture_ppm = final_moisture_ppm
        order.actual_end = actual_end
        order.cycle_confirmed_at = cycle_confirmed_at
        log.info(
            "Order confirmed by operator",
            extra={"order_id": order_id, "spec_met": quality_check_passed},
        )
        return order

    def close(
        self,
        order_id: str,
        sap_confirmation_number: str,
        goods_movement_document: str,
    ) -> Order:
        """Transition: confirmed -> closed."""
        order = self._transition(order_id, "confirmed", "closed")
        order.sap_confirmation_number = sap_confirmation_number
        order.goods_movement_document = goods_movement_document
        log.info(
            "Order closed",
            extra={"order_id": order_id, "sap_conf": sap_confirmation_number},
        )
        return order

    # --- internal ---

    def _transition(self, order_id: str, expected_from: str, to: str) -> Order:
        """Atomically check current status and write new status under the lock."""
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise OrderNotFoundError(f"Order '{order_id}' not found in local store")
            if order.status != expected_from:
                raise InvalidStateTransitionError(
                    order_id=order_id,
                    current=order.status,
                    attempted=to,
                )
            order.status = to
            return order
