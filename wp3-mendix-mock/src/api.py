"""FastAPI application: C4 order state endpoint, operator workflow, and operator UI."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .exceptions import (
    InvalidStateTransitionError,
    OrderNotFoundError,
    SAPClientError,
    WP1ClientError,
    WP5ClientError,
)
from .models import (
    ConfirmRequest,
    CycleEvent,
    GoodsMovementRequest,
    OrderStateResponse,
    SAPConfirmationRequest,
    StartRequest,
)
from .order_service import OrderService
from .sap_client import SAPClient
from .simatic_client import SimaticClient
from .wp1_client import WP1Client
from .wp5_client import WP5Client

log = logging.getLogger(__name__)

app = FastAPI(title="WP3 Mendix Mock", version="1.0.0")

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

_order_service: Optional[OrderService] = None
_sap_client: Optional[SAPClient] = None
_simatic_client: Optional[SimaticClient] = None
_wp1_client: Optional[WP1Client] = None
_wp5_client: Optional[WP5Client] = None
_oven_id: str = "oven-01"


def init_app(
    order_service: OrderService,
    sap_client: SAPClient,
    simatic_client: SimaticClient,
    wp1_client: WP1Client,
    wp5_client: WP5Client,
    oven_id: str = "oven-01",
) -> None:
    global _order_service, _sap_client, _simatic_client, _wp1_client, _wp5_client, _oven_id
    _order_service = order_service
    _sap_client = sap_client
    _simatic_client = simatic_client
    _wp1_client = wp1_client
    _wp5_client = wp5_client
    _oven_id = oven_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _svc() -> OrderService:
    if _order_service is None:
        raise RuntimeError("OrderService not initialised -- call init_app() first")
    return _order_service


# --- health ---

@app.get("/health")
def health() -> dict:
    svc = _svc()
    return {
        "status": "ok",
        "service": "wp3-mendix-mock",
        "order_count": len(svc.all_orders()),
    }


# --- C4: order state ---

@app.get("/orders/{order_id}/state", response_model=OrderStateResponse)
def get_order_state(order_id: str) -> OrderStateResponse:
    """C4 -- current order execution state."""
    try:
        order = _svc().get(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    return OrderStateResponse(
        order_id=order.order_id,
        status=order.status,
        operator_id=order.operator_id,
        cycle_confirmed_at=order.cycle_confirmed_at,
        quality_check_passed=order.quality_check_passed,
    )


# --- operator workflow ---

@app.post("/orders/{order_id}/start")
def start_order(order_id: str, req: StartRequest) -> dict:
    """Transition order released -> in-progress, trigger WP1 cycle, fire C10 event."""
    svc = _svc()

    # Ensure order is in local store -- fetch from SAP if missing
    try:
        svc.get(order_id)
    except OrderNotFoundError:
        try:
            sap_order = _sap_client.get_order(order_id)
        except SAPClientError as exc:
            raise HTTPException(status_code=502, detail=f"SAP unavailable: {exc}")
        svc.upsert_from_sap(sap_order)

    # Fetch material spec for target parameters
    try:
        order = svc.get(order_id)
        material = _sap_client.get_material(order.material_id)
    except SAPClientError as exc:
        raise HTTPException(status_code=502, detail=f"SAP material fetch failed: {exc}")

    actual_start = _utc_now()
    try:
        order = svc.start(order_id, req.operator_id, actual_start)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    order.target_moisture_ppm = float(material.target_moisture_ppm)

    # Trigger WP1 simulator cycle
    try:
        _wp1_client.start_cycle(
            order_id=order_id,
            oven_id=order.oven_id,
            target_moisture_ppm=float(material.target_moisture_ppm),
        )
    except WP1ClientError as exc:
        log.warning("WP1 cycle start failed (non-fatal)", extra={"error": str(exc)})

    # Fire C10 webhook
    event = CycleEvent(
        event_id=str(uuid.uuid4()),
        event_type="cycle_started",
        order_id=order_id,
        oven_id=order.oven_id,
        operator_id=req.operator_id,
        timestamp=actual_start,
        payload={
            "setpoint_temperature_degC": material.target_temperature_degC,
            "setpoint_vacuum_mbar": material.target_vacuum_mbar,
        },
    )
    try:
        _wp5_client.post_event(event)
    except WP5ClientError as exc:
        log.warning("WP5 event post failed (non-fatal)", extra={"error": str(exc)})

    log.info("Order started", extra={"order_id": order_id, "operator_id": req.operator_id})
    return {"order_id": order_id, "status": order.status}


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str, req: ConfirmRequest) -> dict:
    """Transition in-progress -> confirmed -> closed: SAP confirmation + goods movement."""
    svc = _svc()

    try:
        order = svc.get(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    actual_end = _utc_now()
    try:
        order = svc.confirm(
            order_id=order_id,
            quality_check_passed=req.quality_check_passed,
            final_moisture_ppm=req.final_moisture_ppm,
            actual_end=actual_end,
            cycle_confirmed_at=actual_end,
        )
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    spec_met = req.quality_check_passed and (
        order.target_moisture_ppm is None
        or req.final_moisture_ppm < order.target_moisture_ppm
    )

    # C5: post SAP confirmation
    operation_id = f"{order_id}-OPR-010"
    sap_conf_number: str = ""
    try:
        conf_req = SAPConfirmationRequest(
            order_id=order_id,
            operation_id=operation_id,
            confirmed_quantity=1.0,
            actual_start=order.actual_start or actual_end,
            actual_end=actual_end,
            operator_id=order.operator_id or "unknown",
            final_moisture_ppm=req.final_moisture_ppm,
            spec_met=spec_met,
        )
        conf_resp = _sap_client.post_confirmation(conf_req)
        sap_conf_number = conf_resp.get("sap_confirmation_number", "")
    except SAPClientError as exc:
        raise HTTPException(status_code=502, detail=f"SAP confirmation failed: {exc}")

    # C8: post goods movement
    gm_document: str = ""
    try:
        gm_req = GoodsMovementRequest(
            order_id=order_id,
            material_id=order.material_id,
            posting_date=_today_str(),
        )
        gm_resp = _sap_client.post_goods_movement(gm_req)
        gm_document = gm_resp.get("document_number", "")
    except SAPClientError as exc:
        log.warning("Goods movement post failed (non-fatal)", extra={"error": str(exc)})

    order = svc.close(order_id, sap_conf_number, gm_document)

    # C10: fire cycle_confirmed event
    event = CycleEvent(
        event_id=str(uuid.uuid4()),
        event_type="cycle_confirmed",
        order_id=order_id,
        oven_id=order.oven_id,
        operator_id=order.operator_id or "unknown",
        timestamp=actual_end,
        payload={
            "sap_confirmation_number": sap_conf_number,
            "goods_movement_document": gm_document,
        },
    )
    try:
        _wp5_client.post_event(event)
    except WP5ClientError as exc:
        log.warning("WP5 event post failed (non-fatal)", extra={"error": str(exc)})

    log.info(
        "Order confirmed and closed",
        extra={"order_id": order_id, "sap_conf": sap_conf_number},
    )
    return {"order_id": order_id, "status": order.status, "sap_confirmation_number": sap_conf_number}


# --- operator UI ---

@app.get("/orders")
def list_orders() -> list[dict]:
    """Return all orders in local store, merged with RELEASED orders from SAP."""
    try:
        released = _sap_client.get_orders(status="RELEASED")
        for sap_order in released:
            _svc().upsert_from_sap(sap_order)
    except SAPClientError as exc:
        log.warning("SAP order list fetch failed", extra={"error": str(exc)})

    orders = _svc().all_orders()
    return [
        {
            "order_id": o.order_id,
            "material_id": o.material_id,
            "status": o.status,
            "operator_id": o.operator_id,
        }
        for o in orders
    ]


@app.get("/simatic-proxy/{oven_id}")
def simatic_proxy(oven_id: str) -> dict:
    """Proxy WP2 /process-state for the browser UI (avoids cross-origin issues)."""
    try:
        return _simatic_client.get_process_state(oven_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SIMATIC unavailable: {exc}")


@app.get("/", response_class=HTMLResponse)
def operator_ui(request: Request) -> HTMLResponse:
    """Jinja2 operator interface -- decisions: Jinja2 over Streamlit for simplicity."""
    try:
        released = _sap_client.get_orders(status="RELEASED")
        for sap_order in released:
            _svc().upsert_from_sap(sap_order)
    except SAPClientError:
        pass
    orders = _svc().all_orders()
    return templates.TemplateResponse(
        request,
        "operator_ui.html",
        {"orders": orders, "oven_id": _oven_id},
    )
