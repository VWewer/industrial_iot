"""
wp4-sap-mock/src/models.py

Dataclasses for all WP4 domain objects.
Field names and types are authoritative from DOMAIN-MODEL.md Sec.1.1, Sec.1.2, Sec.1.6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


def _fmt_dt(dt: datetime | None) -> str | None:
    """Format a UTC datetime as ISO 8601 with Z suffix. Returns None for None input."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    RELEASED = "RELEASED"
    IN_PROGRESS = "IN_PROGRESS"
    CONFIRMED = "CONFIRMED"
    ABORTED = "ABORTED"
    CLOSED = "CLOSED"


class InsulationClass(str, Enum):
    A = "A"
    B = "B"
    F = "F"
    H = "H"


@dataclass
class ProductionOrder:
    """
    System of record: SAP. Join key across the entire stack.
    DOMAIN-MODEL.md Sec.1.1
    """
    order_id: str                                  # PK, format: ORD-{YYYY}-{5 digits}
    material_id: str                               # FK -> MaterialMaster
    plant: str                                     # enum: regensburg | kirchheim
    oven_id: str                                   # format: oven-{02d}
    planned_start: datetime
    planned_end: datetime
    standard_cycle_minutes: int
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    operator_id: Optional[str] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    sap_confirmation_number: Optional[str] = None
    goods_movement_posted: bool = False

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "material_id": self.material_id,
            "plant": self.plant,
            "oven_id": self.oven_id,
            "planned_start": _fmt_dt(self.planned_start),
            "planned_end": _fmt_dt(self.planned_end),
            "standard_cycle_minutes": self.standard_cycle_minutes,
            "status": self.status.value,
            "operator_id": self.operator_id,
            "actual_start": _fmt_dt(self.actual_start),
            "actual_end": _fmt_dt(self.actual_end),
            "sap_confirmation_number": self.sap_confirmation_number,
            "goods_movement_posted": self.goods_movement_posted,
            "created_at": _fmt_dt(self.created_at),
            "updated_at": _fmt_dt(self.updated_at),
        }


@dataclass
class MaterialMaster:
    """
    System of record: SAP. Read by Mendix and Snowflake Gold layer.
    DOMAIN-MODEL.md Sec.1.2
    """
    material_id: str                               # PK, format: MAT-{4 digits}
    material_description: str                      # max 100 chars
    insulation_class: InsulationClass
    target_moisture_ppm: int                       # drying endpoint
    standard_cycle_minutes: int
    max_cycle_minutes: int                         # > standard_cycle_minutes
    target_temperature_degC: float
    target_vacuum_mbar: float
    weight_kg: float
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "material_description": self.material_description,
            "insulation_class": self.insulation_class.value,
            "target_moisture_ppm": self.target_moisture_ppm,
            "standard_cycle_minutes": self.standard_cycle_minutes,
            "max_cycle_minutes": self.max_cycle_minutes,
            "target_temperature_degC": self.target_temperature_degC,
            "target_vacuum_mbar": self.target_vacuum_mbar,
            "weight_kg": self.weight_kg,
            "updated_at": _fmt_dt(self.updated_at),
        }


@dataclass
class GoodsMovement:
    """
    Goods receipt record posted by Mendix on cycle confirmation.
    Contract C8.
    """
    document_number: str                           # SAP-generated, format: GR-{YYYY}-{6 digits}
    order_id: str
    material_id: str
    movement_type: str                             # GR_PRODUCTION
    quantity: float
    unit: str                                      # EA
    posting_date: str                              # ISO date YYYY-MM-DD
    storage_location: str
    posted_at: datetime

    def to_dict(self) -> dict:
        return {
            "document_number": self.document_number,
            "order_id": self.order_id,
            "material_id": self.material_id,
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "unit": self.unit,
            "posting_date": self.posting_date,
            "storage_location": self.storage_location,
            "posted_at": _fmt_dt(self.posted_at),
            "status": "posted",
        }


@dataclass
class OperationConfirmationRequest:
    """
    Inbound confirmation payload from WP3 (Mendix mock).
    Contract C5 request body. DOMAIN-MODEL.md Sec.1.6.
    """
    order_id: str
    operation_id: str                              # format: {order_id}-OPR-010
    confirmed_quantity: float
    actual_start: datetime
    actual_end: datetime
    operator_id: str
    final_moisture_ppm: float
    spec_met: bool
