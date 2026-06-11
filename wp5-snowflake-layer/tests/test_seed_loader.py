from __future__ import annotations

import json
import os
from unittest.mock import call, patch

import pytest


class TestLoadIfEmpty:
    def test_skips_if_gold_has_rows(self, mock_sf):
        mock_sf.fetchone.return_value = {"row_count": 20}

        from src.seed_loader import load_if_empty

        result = load_if_empty("seed_dir", "sql_dir")

        assert result is False
        mock_sf.execute_many.assert_not_called()

    def test_loads_when_gold_empty(self, mock_sf, tmp_path):
        mock_sf.fetchone.return_value = {"row_count": 0}

        # Write minimal seed files
        materials = [
            {
                "material_id": "MAT-0001",
                "material_description": "Power Transformer 100MVA",
                "insulation_class": "H",
                "target_moisture_ppm": 300,
                "standard_cycle_minutes": 480,
                "max_cycle_minutes": 600,
                "target_temperature_degC": 130.0,
                "target_vacuum_mbar": 5.0,
                "weight_kg": 8500.0,
            }
        ]
        orders = [
            {
                "order_id": "ORD-2026-00042",
                "material_id": "MAT-0001",
                "plant": "regensburg",
                "oven_id": "oven-01",
                "planned_start": "2026-06-03T06:00:00Z",
                "planned_end": "2026-06-03T14:00:00Z",
                "standard_cycle_minutes": 480,
                "status": "CONFIRMED",
            }
        ]
        cycles = [
            {
                "order_id": "ORD-2026-00042",
                "material_id": "MAT-0001",
                "plant": "regensburg",
                "oven_id": "oven-01",
                "operator_id": "OP-001",
                "cycle_start_time": "2026-06-03T06:05:00Z",
                "cycle_end_time": "2026-06-03T14:00:00Z",
                "peak_temperature_degC": 129.7,
                "min_vacuum_mbar": 5.1,
                "final_moisture_ppm": 287.0,
                "sap_confirmation_number": "CONF-001",
                "goods_movement_posted": True,
            }
        ]
        (tmp_path / "material_masters.json").write_text(json.dumps(materials))
        (tmp_path / "production_orders.json").write_text(json.dumps(orders))
        (tmp_path / "historical_cycles.json").write_text(json.dumps(cycles))

        # SQL files so silver/gold transforms don't fail
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "silver_transforms.sql").write_text("SELECT 1")
        (sql_dir / "gold_transforms.sql").write_text("SELECT 1")

        from src.seed_loader import load_if_empty

        result = load_if_empty(str(tmp_path), str(sql_dir))

        assert result is True
        # execute_many should have been called for materials, orders, events, readings
        assert mock_sf.execute_many.call_count >= 3

    def test_historical_cycle_generates_both_mes_events(self, mock_sf, tmp_path):
        mock_sf.fetchone.return_value = {"row_count": 0}

        materials = [{"material_id": "MAT-0001", "target_moisture_ppm": 300}]
        orders = []
        cycles = [
            {
                "order_id": "ORD-TEST-001",
                "oven_id": "oven-01",
                "plant": "regensburg",
                "cycle_start_time": "2026-06-01T06:00:00Z",
                "cycle_end_time": "2026-06-01T14:00:00Z",
                "peak_temperature_degC": 128.0,
                "min_vacuum_mbar": 5.2,
                "final_moisture_ppm": 290.0,
                "goods_movement_posted": False,
            }
        ]
        (tmp_path / "material_masters.json").write_text(json.dumps(materials))
        (tmp_path / "production_orders.json").write_text(json.dumps(orders))
        (tmp_path / "historical_cycles.json").write_text(json.dumps(cycles))

        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        (sql_dir / "silver_transforms.sql").write_text("SELECT 1")
        (sql_dir / "gold_transforms.sql").write_text("SELECT 1")

        from src.seed_loader import load_if_empty

        load_if_empty(str(tmp_path), str(sql_dir))

        # Find the MES events call
        all_calls = mock_sf.execute_many.call_args_list
        events_inserted = 0
        for c in all_calls:
            sql_arg = c[0][0]
            if "bronze_mes_events" in sql_arg:
                rows = c[0][1]
                events_inserted += len(rows)
        assert events_inserted == 2  # cycle_started + cycle_confirmed
