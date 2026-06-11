from __future__ import annotations

import json
import logging

import httpx

from ..exceptions import SAPPullError
from ..snowflake_client import SnowflakeClient

log = logging.getLogger(__name__)

_INSERT_ORDERS_SQL = """
INSERT INTO bronze_sap_production_orders (
    order_id, material_id, plant, oven_id,
    planned_start, planned_end, standard_cycle_minutes, status, raw_payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_MATERIALS_SQL = """
INSERT INTO bronze_sap_material_master (
    material_id, material_description, insulation_class, target_moisture_ppm,
    standard_cycle_minutes, max_cycle_minutes, target_temperature_degC,
    target_vacuum_mbar, weight_kg, raw_payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_GOODS_MOVEMENTS_SQL = """
INSERT INTO bronze_sap_goods_movements (
    document_number, order_id, material_id, movement_type, quantity,
    unit, posting_date, storage_location, posted_at, raw_payload
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


class SAPPuller:
    def __init__(self, sap_api_url: str, snowflake_client: SnowflakeClient) -> None:
        self._sap_url = sap_api_url.rstrip("/")
        self._sf = snowflake_client

    def pull(self) -> None:
        try:
            self._pull_production_orders()
            self._pull_material_masters()
            self._pull_goods_movements()
        except SAPPullError:
            raise
        except Exception as exc:
            raise SAPPullError(f"SAP pull failed: {exc}") from exc

    def _pull_production_orders(self) -> None:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self._sap_url}/odata/v1/ProductionOrders")
            resp.raise_for_status()
        orders = resp.json().get("value", [])
        rows = [
            (
                o.get("order_id"),
                o.get("material_id"),
                o.get("plant"),
                o.get("oven_id"),
                o.get("planned_start"),
                o.get("planned_end"),
                o.get("standard_cycle_minutes"),
                o.get("status"),
                json.dumps(o),
            )
            for o in orders
        ]
        if rows:
            self._sf.execute_many(_INSERT_ORDERS_SQL, rows)
        log.info("SAP production orders pulled", extra={"count": len(rows)})

    def _pull_material_masters(self) -> None:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self._sap_url}/odata/v1/Materials")
            resp.raise_for_status()
        materials = resp.json().get("value", [])
        rows = [
            (
                m.get("material_id"),
                m.get("material_description"),
                m.get("insulation_class"),
                m.get("target_moisture_ppm"),
                m.get("standard_cycle_minutes"),
                m.get("max_cycle_minutes"),
                m.get("target_temperature_degC"),
                m.get("target_vacuum_mbar"),
                m.get("weight_kg"),
                json.dumps(m),
            )
            for m in materials
        ]
        if rows:
            self._sf.execute_many(_INSERT_MATERIALS_SQL, rows)
        log.info("SAP material masters pulled", extra={"count": len(rows)})

    def _pull_goods_movements(self) -> None:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self._sap_url}/odata/v1/GoodsMovements")
            resp.raise_for_status()
        movements = resp.json().get("value", [])
        rows = [
            (
                m.get("document_number"),
                m.get("order_id"),
                m.get("material_id"),
                m.get("movement_type"),
                m.get("quantity"),
                m.get("unit"),
                m.get("posting_date"),
                m.get("storage_location"),
                m.get("posted_at"),
                json.dumps(m),
            )
            for m in movements
        ]
        if rows:
            self._sf.execute_many(_INSERT_GOODS_MOVEMENTS_SQL, rows)
        log.info("SAP goods movements pulled", extra={"count": len(rows)})
