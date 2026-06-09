"""
wp4-sap-mock/src/api.py

FastAPI router for WP4 SAP mock.
Implements contracts C5, C6, C7, C8 and batch export endpoint for WP5.

Endpoint summary:
  GET   /health
  GET   /odata/v1/ProductionOrders                              -- list (C6, C11)
  GET   /odata/v1/ProductionOrders('{order_id}')               -- single order (C6)
  PATCH /odata/v1/ProductionOrders('{order_id}')               -- update status
  POST  /odata/v1/OperationConfirmations                        -- confirmation (C5)
  GET   /odata/v1/Materials('{material_id}')                   -- material master (C7)
  POST  /odata/v1/GoodsMovements                               -- post GR (C8)
  GET   /odata/v1/GoodsMovements                               -- list movements (C11)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .data_store import DataStore
from .exceptions import (
    AlreadyConfirmedError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from .models import OperationConfirmationRequest, OrderStatus

logger = logging.getLogger(__name__)

router = APIRouter()
store: DataStore = None  # injected in main.py


def get_store() -> DataStore:
    return store


# --- Health ------------------------------------------------------------------

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "wp4-sap-mock",
        "orders": len(store.list_orders()),
        "materials": len(store.list_materials()),
    }


# --- Production Orders (C6) --------------------------------------------------

@router.get("/odata/v1/ProductionOrders")
def list_orders(
    status: Optional[str] = Query(default=None, description="Filter by status (e.g. RELEASED)"),
    plant: Optional[str] = Query(default=None, description="Filter by plant"),
):
    """
    List all production orders. Supports OData-style filter params.
    Used by WP3 (C6) and WP5 batch pull (C11).
    """
    try:
        orders = store.list_orders(status=status, plant=plant)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "count": len(orders),
        "value": [o.to_dict() for o in orders],
    }


@router.get("/odata/v1/ProductionOrders('{order_id}')")
def get_order(order_id: str):
    """Single production order by ID. Contract C6."""
    try:
        order = store.get_order(order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return order.to_dict()


class OrderStatusPatch(BaseModel):
    status: str


@router.patch("/odata/v1/ProductionOrders('{order_id}')")
def patch_order_status(order_id: str, body: OrderStatusPatch):
    """Update order status. Used internally and by WP3 for state progression."""
    try:
        new_status = OrderStatus(body.status.upper())
        order = store.update_order_status(order_id, new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.info("Order %s status updated to %s", order_id, new_status.value)
    return order.to_dict()


# --- Operation Confirmations (C5) --------------------------------------------

class ConfirmationRequestBody(BaseModel):
    order_id: str
    operation_id: str = Field(..., description="Format: {order_id}-OPR-010")
    confirmed_quantity: float = Field(..., gt=0)
    actual_start: datetime
    actual_end: datetime
    operator_id: str
    final_moisture_ppm: float = Field(..., ge=0)
    spec_met: bool


@router.post("/odata/v1/OperationConfirmations", status_code=201)
def post_operation_confirmation(body: ConfirmationRequestBody):
    """
    Receive operation confirmation from Mendix (WP3).
    Transitions order to CONFIRMED, generates SAP confirmation number.
    Contract C5.
    """
    req = OperationConfirmationRequest(
        order_id=body.order_id,
        operation_id=body.operation_id,
        confirmed_quantity=body.confirmed_quantity,
        actual_start=body.actual_start,
        actual_end=body.actual_end,
        operator_id=body.operator_id,
        final_moisture_ppm=body.final_moisture_ppm,
        spec_met=body.spec_met,
    )

    try:
        result = store.confirm_order(req)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlreadyConfirmedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.info(
        "Order %s confirmed -- SAP number: %s",
        body.order_id,
        result["sap_confirmation_number"],
    )
    return result


# --- Material Master (C7) ----------------------------------------------------

@router.get("/odata/v1/Materials('{material_id}')")
def get_material(material_id: str):
    """Material master by ID. Contract C7."""
    try:
        mat = store.get_material(material_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return mat.to_dict()


@router.get("/odata/v1/Materials")
def list_materials():
    """List all materials. Used by WP5 batch pull (C11)."""
    mats = store.list_materials()
    return {
        "count": len(mats),
        "value": [m.to_dict() for m in mats],
    }


# --- Goods Movements (C8) ----------------------------------------------------

class GoodsMovementBody(BaseModel):
    order_id: str
    material_id: str
    movement_type: str = "GR_PRODUCTION"
    quantity: float = Field(default=1.0, gt=0)
    unit: str = "EA"
    posting_date: str = Field(..., description="ISO date: YYYY-MM-DD")
    storage_location: str = "WH-01"


@router.post("/odata/v1/GoodsMovements", status_code=201)
def post_goods_movement(body: GoodsMovementBody):
    """
    Post a goods receipt document.
    Returns document number. Contract C8.
    """
    try:
        gm = store.post_goods_movement(body.model_dump())
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("Goods movement posted: %s for order %s", gm.document_number, gm.order_id)
    return gm.to_dict()


@router.get("/odata/v1/GoodsMovements")
def list_goods_movements(
    order_id: Optional[str] = Query(default=None, description="Filter by order ID"),
):
    """
    List goods movements. Used by WP5 batch pull (C11).
    """
    movements = store.list_goods_movements(order_id=order_id)
    return {
        "count": len(movements),
        "value": [gm.to_dict() for gm in movements],
    }
