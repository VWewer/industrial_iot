"""
tests/test_data_store.py

Unit tests for DataStore — seed loading, state machine, confirmations, goods movements.
Run with: pytest tests/test_data_store.py -v
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path

from src.data_store import DataStore
from src.models import OrderStatus
from src.exceptions import (
    NotFoundError,
    InvalidStatusTransitionError,
    AlreadyConfirmedError,
    ValidationError,
)


@pytest.fixture
def store(tmp_path):
    """Create a DataStore with seed data loaded from the real data/ directory."""
    ds = DataStore()
    ds.load_seed_data()
    return ds


class TestSeedLoading:
    def test_materials_loaded(self, store):
        mats = store.list_materials()
        assert len(mats) == 4

    def test_material_ids(self, store):
        ids = {m.material_id for m in store.list_materials()}
        assert ids == {"MAT-0001", "MAT-0002", "MAT-0003", "MAT-0004"}

    def test_orders_loaded(self, store):
        orders = store.list_orders()
        assert len(orders) == 4

    def test_order_statuses_cover_all_states(self, store):
        statuses = {o.status for o in store.list_orders()}
        assert OrderStatus.RELEASED in statuses
        assert OrderStatus.CONFIRMED in statuses
        assert OrderStatus.ABORTED in statuses
        assert OrderStatus.CREATED in statuses

    def test_material_fields(self, store):
        mat = store.get_material("MAT-0001")
        assert mat.material_description == "Power Transformer 100MVA"
        assert mat.insulation_class.value == "H"
        assert mat.target_moisture_ppm == 300
        assert mat.standard_cycle_minutes == 480
        assert mat.max_cycle_minutes == 600
        assert mat.target_temperature_degC == 130.0
        assert mat.target_vacuum_mbar == 5.0
        assert mat.weight_kg == 8500.0

    def test_released_order_fields(self, store):
        order = store.get_order("ORD-2026-00042")
        assert order.status == OrderStatus.RELEASED
        assert order.material_id == "MAT-0001"
        assert order.plant == "regensburg"
        assert order.oven_id == "oven-01"
        assert order.sap_confirmation_number is None
        assert order.goods_movement_posted is False


class TestOrderFiltering:
    def test_filter_by_status(self, store):
        released = store.list_orders(status="RELEASED")
        assert all(o.status == OrderStatus.RELEASED for o in released)
        assert len(released) == 1

    def test_filter_by_plant(self, store):
        orders = store.list_orders(plant="regensburg")
        assert len(orders) == 4

    def test_invalid_status_raises(self, store):
        with pytest.raises(ValidationError):
            store.list_orders(status="INVALID_STATUS")

    def test_not_found_raises(self, store):
        with pytest.raises(NotFoundError):
            store.get_order("ORD-DOES-NOT-EXIST")


class TestStateTransitions:
    def test_released_to_in_progress(self, store):
        order = store.update_order_status("ORD-2026-00042", OrderStatus.IN_PROGRESS)
        assert order.status == OrderStatus.IN_PROGRESS

    def test_invalid_transition_raises(self, store):
        # CONFIRMED → RELEASED is not allowed
        with pytest.raises(InvalidStatusTransitionError):
            store.update_order_status("ORD-2026-00041", OrderStatus.RELEASED)

    def test_aborted_cannot_transition(self, store):
        with pytest.raises(InvalidStatusTransitionError):
            store.update_order_status("ORD-2026-00039", OrderStatus.RELEASED)


class TestConfirmOrder:
    def _make_req(self, order_id="ORD-2026-00042"):
        from src.models import OperationConfirmationRequest
        return OperationConfirmationRequest(
            order_id=order_id,
            operation_id=f"{order_id}-OPR-010",
            confirmed_quantity=1.0,
            actual_start=datetime(2026, 6, 3, 6, 5, tzinfo=timezone.utc),
            actual_end=datetime(2026, 6, 3, 13, 58, tzinfo=timezone.utc),
            operator_id="OP-007",
            final_moisture_ppm=287.4,
            spec_met=True,
        )

    def test_confirm_released_order(self, store):
        result = store.confirm_order(self._make_req())
        assert result["order_id"] == "ORD-2026-00042"
        assert result["status"] == "CONFIRMED"
        assert result["sap_confirmation_number"].startswith("CONF-")

    def test_confirm_updates_order(self, store):
        store.confirm_order(self._make_req())
        order = store.get_order("ORD-2026-00042")
        assert order.status == OrderStatus.CONFIRMED
        assert order.sap_confirmation_number is not None
        assert order.operator_id == "OP-007"

    def test_double_confirm_raises(self, store):
        store.confirm_order(self._make_req())
        with pytest.raises(AlreadyConfirmedError):
            store.confirm_order(self._make_req())

    def test_confirm_not_found_raises(self, store):
        req = self._make_req("ORD-NOT-REAL")
        with pytest.raises(NotFoundError):
            store.confirm_order(req)


class TestGoodsMovements:
    def test_post_goods_movement(self, store):
        payload = {
            "order_id": "ORD-2026-00042",
            "material_id": "MAT-0001",
            "movement_type": "GR_PRODUCTION",
            "quantity": 1,
            "unit": "EA",
            "posting_date": "2026-06-03",
            "storage_location": "WH-01",
        }
        gm = store.post_goods_movement(payload)
        assert gm.document_number.startswith("GR-")
        assert gm.order_id == "ORD-2026-00042"
        assert gm.to_dict()["status"] == "posted"

    def test_post_marks_order(self, store):
        payload = {"order_id": "ORD-2026-00042", "posting_date": "2026-06-03"}
        store.post_goods_movement(payload)
        order = store.get_order("ORD-2026-00042")
        assert order.goods_movement_posted is True

    def test_list_by_order(self, store):
        payload = {"order_id": "ORD-2026-00042", "posting_date": "2026-06-03"}
        store.post_goods_movement(payload)
        movements = store.list_goods_movements(order_id="ORD-2026-00042")
        assert len(movements) == 1

    def test_post_missing_order_raises(self, store):
        with pytest.raises(NotFoundError):
            store.post_goods_movement({"order_id": "ORD-FAKE", "posting_date": "2026-06-03"})
