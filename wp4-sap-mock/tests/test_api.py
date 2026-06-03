"""
tests/test_api.py

Integration-style tests for WP4 FastAPI endpoints.
Uses TestClient — no real HTTP, no running server required.
Run with: pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src import api as api_module
from src.data_store import DataStore


@pytest.fixture(autouse=True)
def fresh_store():
    """Reset the data store before each test."""
    ds = DataStore()
    ds.load_seed_data()
    api_module.store = ds
    yield ds


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["orders"] == 4
        assert data["materials"] == 4


class TestProductionOrders:
    def test_list_all_orders(self, client):
        r = client.get("/odata/v1/ProductionOrders")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 4
        assert len(data["value"]) == 4

    def test_filter_by_status(self, client):
        r = client.get("/odata/v1/ProductionOrders?status=RELEASED")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["value"][0]["status"] == "RELEASED"

    def test_filter_by_plant(self, client):
        r = client.get("/odata/v1/ProductionOrders?plant=regensburg")
        assert r.status_code == 200
        assert r.json()["count"] == 4

    def test_get_single_order(self, client):
        r = client.get("/odata/v1/ProductionOrders('ORD-2026-00042')")
        assert r.status_code == 200
        data = r.json()
        assert data["order_id"] == "ORD-2026-00042"
        assert data["material_id"] == "MAT-0001"
        assert data["status"] == "RELEASED"

    def test_get_order_not_found(self, client):
        r = client.get("/odata/v1/ProductionOrders('ORD-DOES-NOT-EXIST')")
        assert r.status_code == 404

    def test_patch_order_status(self, client):
        r = client.patch(
            "/odata/v1/ProductionOrders('ORD-2026-00042')",
            json={"status": "IN_PROGRESS"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "IN_PROGRESS"

    def test_patch_invalid_transition(self, client):
        # CONFIRMED → RELEASED is not valid
        r = client.patch(
            "/odata/v1/ProductionOrders('ORD-2026-00041')",
            json={"status": "RELEASED"},
        )
        assert r.status_code == 409

    def test_order_response_has_all_fields(self, client):
        r = client.get("/odata/v1/ProductionOrders('ORD-2026-00042')")
        data = r.json()
        required_fields = [
            "order_id", "material_id", "plant", "oven_id",
            "planned_start", "planned_end", "standard_cycle_minutes",
            "status", "operator_id", "actual_start", "actual_end",
            "sap_confirmation_number", "goods_movement_posted",
            "created_at", "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestOperationConfirmations:
    CONFIRM_PAYLOAD = {
        "order_id": "ORD-2026-00042",
        "operation_id": "ORD-2026-00042-OPR-010",
        "confirmed_quantity": 1.0,
        "actual_start": "2026-06-03T06:05:00Z",
        "actual_end": "2026-06-03T13:58:00Z",
        "operator_id": "OP-007",
        "final_moisture_ppm": 287.4,
        "spec_met": True,
    }

    def test_post_confirmation(self, client):
        r = client.post("/odata/v1/OperationConfirmations", json=self.CONFIRM_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["order_id"] == "ORD-2026-00042"
        assert data["status"] == "CONFIRMED"
        assert data["sap_confirmation_number"].startswith("CONF-")
        assert "posted_at" in data

    def test_order_status_updated_after_confirmation(self, client):
        client.post("/odata/v1/OperationConfirmations", json=self.CONFIRM_PAYLOAD)
        r = client.get("/odata/v1/ProductionOrders('ORD-2026-00042')")
        assert r.json()["status"] == "CONFIRMED"
        assert r.json()["sap_confirmation_number"] is not None

    def test_double_confirm_returns_409(self, client):
        client.post("/odata/v1/OperationConfirmations", json=self.CONFIRM_PAYLOAD)
        r = client.post("/odata/v1/OperationConfirmations", json=self.CONFIRM_PAYLOAD)
        assert r.status_code == 409

    def test_confirm_not_found_returns_404(self, client):
        payload = {**self.CONFIRM_PAYLOAD, "order_id": "ORD-FAKE"}
        r = client.post("/odata/v1/OperationConfirmations", json=payload)
        assert r.status_code == 404


class TestMaterials:
    def test_get_material(self, client):
        r = client.get("/odata/v1/Materials('MAT-0001')")
        assert r.status_code == 200
        data = r.json()
        assert data["material_id"] == "MAT-0001"
        assert data["material_description"] == "Power Transformer 100MVA"
        assert data["insulation_class"] == "H"
        assert data["target_moisture_ppm"] == 300

    def test_material_has_all_fields(self, client):
        r = client.get("/odata/v1/Materials('MAT-0001')")
        data = r.json()
        required_fields = [
            "material_id", "material_description", "insulation_class",
            "target_moisture_ppm", "standard_cycle_minutes", "max_cycle_minutes",
            "target_temperature_degC", "target_vacuum_mbar", "weight_kg", "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_material_not_found(self, client):
        r = client.get("/odata/v1/Materials('MAT-9999')")
        assert r.status_code == 404

    def test_list_materials(self, client):
        r = client.get("/odata/v1/Materials")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 4


class TestGoodsMovements:
    GR_PAYLOAD = {
        "order_id": "ORD-2026-00042",
        "material_id": "MAT-0001",
        "movement_type": "GR_PRODUCTION",
        "quantity": 1,
        "unit": "EA",
        "posting_date": "2026-06-03",
        "storage_location": "WH-01",
    }

    def test_post_goods_movement(self, client):
        r = client.post("/odata/v1/GoodsMovements", json=self.GR_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["document_number"].startswith("GR-")
        assert data["status"] == "posted"
        assert "posted_at" in data

    def test_goods_movement_marks_order(self, client):
        client.post("/odata/v1/GoodsMovements", json=self.GR_PAYLOAD)
        r = client.get("/odata/v1/ProductionOrders('ORD-2026-00042')")
        assert r.json()["goods_movement_posted"] is True

    def test_list_goods_movements(self, client):
        client.post("/odata/v1/GoodsMovements", json=self.GR_PAYLOAD)
        r = client.get("/odata/v1/GoodsMovements")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1

    def test_list_goods_movements_filter_by_order(self, client):
        client.post("/odata/v1/GoodsMovements", json=self.GR_PAYLOAD)
        r = client.get("/odata/v1/GoodsMovements?order_id=ORD-2026-00042")
        assert r.json()["count"] == 1
        r2 = client.get("/odata/v1/GoodsMovements?order_id=ORD-2026-00041")
        assert r2.json()["count"] == 0

    def test_post_gr_for_missing_order(self, client):
        payload = {**self.GR_PAYLOAD, "order_id": "ORD-FAKE"}
        r = client.post("/odata/v1/GoodsMovements", json=payload)
        assert r.status_code == 404
