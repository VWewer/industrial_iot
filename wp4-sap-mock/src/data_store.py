"""
wp4-sap-mock/src/data_store.py

In-memory data store for WP4.
Loads seed data on startup, manages state transitions, generates document numbers.

State machine (DOMAIN-MODEL.md Sec.2):
  CREATED -> RELEASED -> IN_PROGRESS -> CONFIRMED -> CLOSED
  Any state -> ABORTED (except CONFIRMED/CLOSED)
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .exceptions import (
    AlreadyConfirmedError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from .models import (
    GoodsMovement,
    InsulationClass,
    MaterialMaster,
    OperationConfirmationRequest,
    OrderStatus,
    ProductionOrder,
    _fmt_dt,
)

logger = logging.getLogger(__name__)

# Valid forward transitions
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.RELEASED, OrderStatus.ABORTED},
    OrderStatus.RELEASED: {OrderStatus.IN_PROGRESS, OrderStatus.ABORTED},
    OrderStatus.IN_PROGRESS: {OrderStatus.CONFIRMED, OrderStatus.ABORTED},
    OrderStatus.CONFIRMED: {OrderStatus.CLOSED},
    OrderStatus.ABORTED: set(),
    OrderStatus.CLOSED: set(),
}

DATA_DIR = Path(__file__).parent.parent / "data"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_conf_number(year: int, sequence: int) -> str:
    return f"CONF-{year}-{sequence:05d}"


def _generate_gr_number(year: int, sequence: int) -> str:
    return f"GR-{year}-{sequence:06d}"


class DataStore:
    """Thread-safe in-memory store for orders, materials, and goods movements."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._orders: dict[str, ProductionOrder] = {}
        self._materials: dict[str, MaterialMaster] = {}
        self._goods_movements: list[GoodsMovement] = []
        self._conf_sequence: int = 900
        self._gr_sequence: int = 3900

    # --- Seed loading --------------------------------------------------------

    def load_seed_data(self) -> None:
        """Load seed orders and materials from JSON files in data/."""
        self._load_materials()
        self._load_orders()
        logger.info(
            "Seed data loaded: %d orders, %d materials",
            len(self._orders),
            len(self._materials),
        )

    def _load_materials(self) -> None:
        path = DATA_DIR / "seed_materials.json"
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        for r in records:
            mat = MaterialMaster(
                material_id=r["material_id"],
                material_description=r["material_description"],
                insulation_class=InsulationClass(r["insulation_class"]),
                target_moisture_ppm=int(r["target_moisture_ppm"]),
                standard_cycle_minutes=int(r["standard_cycle_minutes"]),
                max_cycle_minutes=int(r["max_cycle_minutes"]),
                target_temperature_degC=float(r["target_temperature_degC"]),
                target_vacuum_mbar=float(r["target_vacuum_mbar"]),
                weight_kg=float(r["weight_kg"]),
                updated_at=_parse_dt(r["updated_at"]),
            )
            self._materials[mat.material_id] = mat
        logger.debug("Loaded %d materials", len(self._materials))

    def _load_orders(self) -> None:
        path = DATA_DIR / "seed_orders.json"
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        for r in records:
            order = ProductionOrder(
                order_id=r["order_id"],
                material_id=r["material_id"],
                plant=r["plant"],
                oven_id=r["oven_id"],
                planned_start=_parse_dt(r["planned_start"]),
                planned_end=_parse_dt(r["planned_end"]),
                standard_cycle_minutes=int(r["standard_cycle_minutes"]),
                status=OrderStatus(r["status"]),
                operator_id=r.get("operator_id"),
                actual_start=_parse_dt(r.get("actual_start")),
                actual_end=_parse_dt(r.get("actual_end")),
                sap_confirmation_number=r.get("sap_confirmation_number"),
                goods_movement_posted=bool(r.get("goods_movement_posted", False)),
                created_at=_parse_dt(r["created_at"]),
                updated_at=_parse_dt(r["updated_at"]),
            )
            self._orders[order.order_id] = order
        logger.debug("Loaded %d orders", len(self._orders))

    # --- Orders --------------------------------------------------------------

    def get_order(self, order_id: str) -> ProductionOrder:
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise NotFoundError(f"Order not found: {order_id}")
            return order

    def list_orders(
        self,
        status: Optional[str] = None,
        plant: Optional[str] = None,
    ) -> list[ProductionOrder]:
        with self._lock:
            orders = list(self._orders.values())
        if status:
            try:
                status_enum = OrderStatus(status.upper())
            except ValueError:
                raise ValidationError(f"Invalid status: {status}")
            orders = [o for o in orders if o.status == status_enum]
        if plant:
            orders = [o for o in orders if o.plant == plant]
        return orders

    def update_order_status(self, order_id: str, new_status: OrderStatus) -> ProductionOrder:
        with self._lock:
            order = self.get_order(order_id)
            if new_status not in ALLOWED_TRANSITIONS[order.status]:
                raise InvalidStatusTransitionError(
                    f"Cannot transition order {order_id} from {order.status.value} to {new_status.value}"
                )
            order.status = new_status
            order.updated_at = _now()
            return order

    def confirm_order(self, req: OperationConfirmationRequest) -> dict:
        """
        Process an OperationConfirmation (C5).
        Transitions order IN_PROGRESS -> CONFIRMED, assigns confirmation number.
        """
        with self._lock:
            order = self.get_order(req.order_id)

            if order.status == OrderStatus.CONFIRMED:
                raise AlreadyConfirmedError(
                    f"Order {req.order_id} is already confirmed: {order.sap_confirmation_number}"
                )
            if order.status not in (OrderStatus.IN_PROGRESS, OrderStatus.RELEASED):
                raise InvalidStatusTransitionError(
                    f"Cannot confirm order {req.order_id} with status {order.status.value}"
                )

            self._conf_sequence += 1
            year = req.actual_end.year
            conf_number = _generate_conf_number(year, self._conf_sequence)

            order.status = OrderStatus.CONFIRMED
            order.operator_id = req.operator_id
            order.actual_start = req.actual_start
            order.actual_end = req.actual_end
            order.sap_confirmation_number = conf_number
            order.updated_at = _now()

            posted_at = _now()
            return {
                "order_id": order.order_id,
                "sap_confirmation_number": conf_number,
                "status": order.status.value,
                "posted_at": _fmt_dt(posted_at),
            }

    # --- Materials -----------------------------------------------------------

    def get_material(self, material_id: str) -> MaterialMaster:
        with self._lock:
            mat = self._materials.get(material_id)
            if mat is None:
                raise NotFoundError(f"Material not found: {material_id}")
            return mat

    def list_materials(self) -> list[MaterialMaster]:
        with self._lock:
            return list(self._materials.values())

    # --- Goods movements -----------------------------------------------------

    def post_goods_movement(self, payload: dict) -> GoodsMovement:
        """Create a goods movement document (C8) and link it to the order."""
        with self._lock:
            order_id = payload.get("order_id")
            if not order_id:
                raise ValidationError("order_id is required")

            order = self.get_order(order_id)

            self._gr_sequence += 1
            year = _now().year
            doc_number = _generate_gr_number(year, self._gr_sequence)
            posted_at = _now()

            gm = GoodsMovement(
                document_number=doc_number,
                order_id=order_id,
                material_id=payload.get("material_id", order.material_id),
                movement_type=payload.get("movement_type", "GR_PRODUCTION"),
                quantity=float(payload.get("quantity", 1)),
                unit=payload.get("unit", "EA"),
                posting_date=payload.get("posting_date", posted_at.strftime("%Y-%m-%d")),
                storage_location=payload.get("storage_location", "WH-01"),
                posted_at=posted_at,
            )
            self._goods_movements.append(gm)

            # Mark order as goods movement posted
            order.goods_movement_posted = True
            order.updated_at = _now()

            logger.info("Posted goods movement %s for order %s", doc_number, order_id)
            return gm

    def list_goods_movements(
        self,
        order_id: Optional[str] = None,
    ) -> list[GoodsMovement]:
        with self._lock:
            movements = list(self._goods_movements)
        if order_id:
            movements = [gm for gm in movements if gm.order_id == order_id]
        return movements
