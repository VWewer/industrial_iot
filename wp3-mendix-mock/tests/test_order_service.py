"""Tests for order_service.py -- state machine transitions and store operations."""
from __future__ import annotations

import pytest

from src.exceptions import InvalidStateTransitionError, OrderNotFoundError
from src.models import Order
from src.order_service import OrderService


def _sap_payload(order_id: str = "ORD-2026-00001") -> dict:
    return {
        "order_id": order_id,
        "material_id": "MAT-0001",
        "plant": "regensburg",
        "oven_id": "oven-01",
        "status": "RELEASED",
    }


TS = "2026-06-09T08:00:00.000Z"
TS2 = "2026-06-09T16:00:00.000Z"


class TestUpsertFromSAP:
    def test_creates_order_with_released_status(self):
        svc = OrderService()
        order = svc.upsert_from_sap(_sap_payload())
        assert order.order_id == "ORD-2026-00001"
        assert order.status == "released"

    def test_idempotent_when_order_exists(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        svc.start("ORD-2026-00001", "OP-007", TS)  # change status to in-progress
        svc.upsert_from_sap(_sap_payload())          # upsert again
        order = svc.get("ORD-2026-00001")
        assert order.status == "in-progress"  # preserves local state

    def test_multiple_orders_stored_independently(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload("ORD-2026-00001"))
        svc.upsert_from_sap(_sap_payload("ORD-2026-00002"))
        assert svc.get("ORD-2026-00001").order_id == "ORD-2026-00001"
        assert svc.get("ORD-2026-00002").order_id == "ORD-2026-00002"


class TestGetOrder:
    def test_raises_order_not_found_for_unknown_id(self):
        svc = OrderService()
        with pytest.raises(OrderNotFoundError):
            svc.get("ORD-NONEXISTENT")

    def test_returns_order_when_exists(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        order = svc.get("ORD-2026-00001")
        assert order.material_id == "MAT-0001"


class TestStartTransition:
    def test_released_to_in_progress(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        order = svc.start("ORD-2026-00001", "OP-007", TS)
        assert order.status == "in-progress"
        assert order.operator_id == "OP-007"
        assert order.actual_start == TS

    def test_raises_on_wrong_state(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        svc.start("ORD-2026-00001", "OP-007", TS)
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            svc.start("ORD-2026-00001", "OP-007", TS)
        assert exc_info.value.current == "in-progress"
        assert exc_info.value.attempted == "in-progress"


class TestConfirmTransition:
    def _started(self, svc: OrderService) -> None:
        svc.upsert_from_sap(_sap_payload())
        svc.start("ORD-2026-00001", "OP-007", TS)

    def test_in_progress_to_confirmed(self):
        svc = OrderService()
        self._started(svc)
        order = svc.confirm("ORD-2026-00001", True, 250.0, TS2, TS2)
        assert order.status == "confirmed"
        assert order.quality_check_passed is True
        assert order.final_moisture_ppm == 250.0
        assert order.actual_end == TS2

    def test_cannot_confirm_released_order(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        with pytest.raises(InvalidStateTransitionError):
            svc.confirm("ORD-2026-00001", True, 250.0, TS2, TS2)

    def test_failed_quality_check_recorded(self):
        svc = OrderService()
        self._started(svc)
        order = svc.confirm("ORD-2026-00001", False, 900.0, TS2, TS2)
        assert order.quality_check_passed is False


class TestCloseTransition:
    def _confirmed(self, svc: OrderService) -> None:
        svc.upsert_from_sap(_sap_payload())
        svc.start("ORD-2026-00001", "OP-007", TS)
        svc.confirm("ORD-2026-00001", True, 250.0, TS2, TS2)

    def test_confirmed_to_closed(self):
        svc = OrderService()
        self._confirmed(svc)
        order = svc.close("ORD-2026-00001", "CONF-2026-00001", "GR-2026-00001")
        assert order.status == "closed"
        assert order.sap_confirmation_number == "CONF-2026-00001"
        assert order.goods_movement_document == "GR-2026-00001"

    def test_cannot_close_released_order(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload())
        with pytest.raises(InvalidStateTransitionError):
            svc.close("ORD-2026-00001", "CONF-X", "GR-X")


class TestListByStatus:
    def test_list_released(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload("ORD-2026-00001"))
        svc.upsert_from_sap(_sap_payload("ORD-2026-00002"))
        svc.start("ORD-2026-00001", "OP-007", TS)
        released = svc.list_by_status("released")
        assert len(released) == 1
        assert released[0].order_id == "ORD-2026-00002"

    def test_all_orders(self):
        svc = OrderService()
        svc.upsert_from_sap(_sap_payload("ORD-2026-00001"))
        svc.upsert_from_sap(_sap_payload("ORD-2026-00002"))
        assert len(svc.all_orders()) == 2
