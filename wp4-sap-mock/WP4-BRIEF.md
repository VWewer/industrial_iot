# WP4 — SAP Mock

## Status: PHASE 3 COMPLETE — ready for seam validation (Phase 4)

## Role in the architecture
WP4 simulates SAP S/4HANA's OData interface. It is the system of record for production orders, material master data, and goods movements. In the real architecture, Mendix is the only layer that talks to SAP. WP4 enforces that boundary — WP2 and WP1 never call WP4.

WP4 also serves as the SAP data source for WP5's scheduled batch ingestion (reference data pull, C11).

## What this WP produces
**Contract C6** — `GET /odata/v1/ProductionOrders(...)` — production order data
**Contract C7** — `GET /odata/v1/Materials(...)` — material master
**Contract C8** — `POST /odata/v1/GoodsMovements` — goods receipt posting
**Contract C5** — `POST /odata/v1/OperationConfirmations` — confirmation from Mendix
**Contract C11** — all GET endpoints above serve as the WP5 batch pull source

See `contracts/interface-contracts.md → C5, C6, C7, C8, C11`.

## What this WP consumes
Nothing upstream. WP4 is a source system.

## Tech stack
- Python 3.11+
- `fastapi==0.111.0` + `uvicorn`
- `pydantic==2.7.1`
- Standard `logging`, `dataclasses`, `json`, `threading`

## Configuration
```
SAP_API_PORT=8003
PLANT_ID=regensburg
```

## Folder structure
```
wp4-sap-mock/
  WP4-BRIEF.md          ← rename from WP-BRIEF.md
  README.md             ← sample outputs, seed data table, state machine diagram
  Dockerfile
  requirements.txt
  .env.example
  src/
    __init__.py
    main.py             Entry point — FastAPI app + startup seed loader
    data_store.py       In-memory store + seed loader + state machine
    api.py              FastAPI router — all endpoints
    models.py           ProductionOrder, MaterialMaster, GoodsMovement, OperationConfirmationRequest
    exceptions.py       NotFoundError, InvalidStatusTransitionError, AlreadyConfirmedError, ValidationError
  data/
    seed_orders.json    4 production orders (CREATED/RELEASED/CONFIRMED/ABORTED)
    seed_materials.json 4 transformer material masters
  tests/
    __init__.py
    test_data_store.py  Unit tests — seed loading, state machine, confirmations, GR
    test_api.py         Endpoint tests via FastAPI TestClient (43 tests, all passing)
```

## Seed data

| order_id | material_id | status | notes |
|---|---|---|---|
| ORD-2026-00042 | MAT-0001 | RELEASED | Active demo order — 100MVA Power Transformer |
| ORD-2026-00041 | MAT-0002 | CONFIRMED | Most recent historical — 1MVA Distribution Transformer |
| ORD-2026-00039 | MAT-0003 | ABORTED | Deviation case — CT 36kV |
| ORD-2026-00043 | MAT-0004 | CREATED | Queued — 400MVA Power Transformer |

## State machine
```
CREATED → RELEASED → IN_PROGRESS → CONFIRMED → CLOSED
   ↓          ↓           ↓
ABORTED   ABORTED     ABORTED
```

## Definition of Done
- [x] All C5, C6, C7, C8 endpoints respond with schema-compliant payloads
- [x] Seed data loaded on startup — 4 orders, 4 materials, all required statuses covered
- [x] Order status transitions correctly on confirmation POST
- [x] Goods movement document number generated and returned on POST
- [x] Batch export endpoint returns filterable list for WP5 pull (C11)
- [x] Sample responses documented in README
- [x] 43/43 tests passing (test_data_store.py + test_api.py)
- [ ] Seam validation with WP3 (Phase 4) — pending WP3 implementation
- [ ] Seam validation with WP5 (Phase 4) — pending WP5 implementation

## Open items
- [ ] Confirm WP5 pull interval for demo (currently 60s default, configurable via SAP_PULL_INTERVAL_S)
- [ ] `on_event` deprecation warnings in FastAPI — cosmetic only, migrate to `lifespan` context manager before WP7 integration if time permits

## Session handover notes

**Session date:** June 2026

**What was completed this session:**
- Full WP4 implementation from scratch — all files per folder structure above
- All four contracts (C5, C6, C7, C8) implemented and tested
- Seed data: 4 orders (CREATED/RELEASED/CONFIRMED/ABORTED) + 4 materials aligned to DOMAIN-MODEL.md §8
- 43 tests written and passing (unit + API layer)
- Dockerfile created — service starts with `docker-compose up wp4`

**Contracts fixed upstream (interface-contracts.md v1.1):**
- C5 endpoint corrected to `POST /odata/v1/OperationConfirmations` (was `/Confirm` action)
- C5 request body rewritten to match DOMAIN-MODEL §1.6 SAPConfirmation schema
- C6 response expanded to full ProductionOrder schema (was missing 8 fields)
- C7 field names corrected: `material_description`, `target_temperature_degC`, `target_vacuum_mbar`; added `max_cycle_minutes`, `weight_kg`, `updated_at`
- C12 field names corrected: `cycle_start_time`, `cycle_end_time`, `spec_met`, added `oven_id`, `goods_movement_posted`
- Sensor type enum corrected across C1/C2/C3: `moisture` (was `moisture-offgas`), removed `heater-power`
- All material IDs and order IDs updated to DOMAIN-MODEL format (`MAT-0001`, `ORD-2026-*`)

**Next action for WP4:** Phase 4 seam validation when WP3 (Mendix mock) is ready to call C5, C6, C7, C8.

**Next WP to implement:** WP1 (Sensor Simulator) — no upstream dependencies, MQTT schema now stable in contracts v1.1.
