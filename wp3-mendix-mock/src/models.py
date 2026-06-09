"""Domain models for WP3: order state machine, SAP payloads, and API contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, field_validator


# --- internal order entity ---

@dataclass
class Order:
    """Mutable per-order state managed by OrderService."""

    order_id: str
    material_id: str
    plant: str
    oven_id: str
    status: str                             # released | in-progress | confirmed | closed
    operator_id: Optional[str] = None
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None
    cycle_confirmed_at: Optional[str] = None
    quality_check_passed: Optional[bool] = None
    target_moisture_ppm: Optional[float] = None
    final_moisture_ppm: Optional[float] = None
    sap_confirmation_number: Optional[str] = None
    goods_movement_document: Optional[str] = None


@dataclass
class MaterialSpec:
    """C7 material master data fetched from WP4 on cycle start."""

    material_id: str
    material_description: str
    target_moisture_ppm: int
    target_temperature_degC: float
    target_vacuum_mbar: float
    standard_cycle_minutes: int
    max_cycle_minutes: int
    weight_kg: float


# --- C4 response ---

class OrderStateResponse(BaseModel):
    """GET /orders/{order_id}/state -- C4 contract."""

    order_id: str
    status: str                             # released | in-progress | confirmed | closed
    operator_id: Optional[str]
    cycle_confirmed_at: Optional[str]
    quality_check_passed: Optional[bool]


# --- operator API request models ---

class StartRequest(BaseModel):
    operator_id: str

    @field_validator("operator_id")
    @classmethod
    def operator_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("operator_id must not be empty")
        return v


class ConfirmRequest(BaseModel):
    quality_check_passed: bool
    final_moisture_ppm: float

    @field_validator("final_moisture_ppm")
    @classmethod
    def moisture_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("final_moisture_ppm must be non-negative")
        return v


# --- C5 SAP confirmation request ---

@dataclass
class SAPConfirmationRequest:
    """Body sent to WP4 POST /odata/v1/OperationConfirmations (C5)."""

    order_id: str
    operation_id: str
    confirmed_quantity: float
    actual_start: str
    actual_end: str
    operator_id: str
    final_moisture_ppm: float
    spec_met: bool

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "operation_id": self.operation_id,
            "confirmed_quantity": self.confirmed_quantity,
            "actual_start": self.actual_start,
            "actual_end": self.actual_end,
            "operator_id": self.operator_id,
            "final_moisture_ppm": self.final_moisture_ppm,
            "spec_met": self.spec_met,
        }


# --- C8 goods movement request ---

@dataclass
class GoodsMovementRequest:
    """Body sent to WP4 POST /odata/v1/GoodsMovements (C8)."""

    order_id: str
    material_id: str
    movement_type: str = "GR_PRODUCTION"
    quantity: int = 1
    unit: str = "EA"
    posting_date: str = ""
    storage_location: str = "WH-01"

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "material_id": self.material_id,
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "unit": self.unit,
            "posting_date": self.posting_date,
            "storage_location": self.storage_location,
        }


# --- C10 MES event webhook ---

@dataclass
class CycleEvent:
    """Webhook payload sent to WP5 POST /events (C10)."""

    event_id: str
    event_type: str    # cycle_started | cycle_confirmed | cycle_aborted | cycle_timeout
    order_id: str
    oven_id: str
    operator_id: str
    timestamp: str
    payload: dict

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "order_id": self.order_id,
            "oven_id": self.oven_id,
            "operator_id": self.operator_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
