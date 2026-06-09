# WP4 — SAP Mock

## Status: PHASE 4 COMPLETE

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
- [x] Producer-side seam validation (Phase 4) — 18/18 PASS (2026-06-03)
- [ ] Consumer-side seam validation with WP3 — pending WP3 implementation
- [ ] Consumer-side seam validation with WP5 — pending WP5 implementation

## Open items
- [ ] Confirm WP5 pull interval for demo (currently 60s default, configurable via SAP_PULL_INTERVAL_S)
- [x] `on_event` deprecation -- migrated to `lifespan` context manager (2026-06-03)

## Session handover notes

**Session 1 (June 2026):** Full WP4 implementation. All contracts C5-C8 + C11. 43/43 tests. Contracts v1.1 alignment (8 field corrections). Dockerfile created.

**Session 2 (2026-06-03/04):** Phase 4 producer seam check.
- Fixed P-08 (timestamps): all `to_dict()` now use `_fmt_dt()` helper, outputs `Z` suffix not `+00:00`
- Fixed P-12 (ASCII): removed box-drawing chars, Unicode arrows, em-dashes from all 4 source files
- Fixed P-11 (pytest.ini): created `pytest.ini` with filterwarnings
- Migrated `@app.on_event("startup")` to `lifespan` context manager
- Created validators: `validate_c5_confirmation_response.py`, `validate_c6_production_order.py`, `validate_c7_material_master.py`, `validate_c8_goods_movement.py`
- Phase 4 result: 18/18 PASS (4 orders x C6, 4 materials x C7, C5 response, C8 response)
- 43/43 tests still passing, 0 warnings

**Next action for WP4:** Consumer-side seam validation when WP3 and WP5 are ready. No blocking issues.
