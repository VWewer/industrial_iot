# WP3 — Mendix Mock

## Status: NOT STARTED

> **Phase 1 gate (mandatory before writing code):**
> Run the Level 3 harmony check: read `checks/project-patterns.md` and tick off all 12 patterns against your planned structure. Takes ~10 minutes. See `SDLC.md` Phase 1 step 5 and `AI-DEV.md` Section 15.

## Role in the architecture
WP3 simulates the Mendix application layer. In the real system, Mendix is the operator-facing web application and the SAP integration hub — it reads production orders from SAP, presents them to operators, receives confirmations, and writes them back to SAP.

WP3 implements this as a lightweight FastAPI service with a simple operator UI (served as HTML or a minimal Streamlit page). It is the only layer that talks to SAP (WP4) — neither WP1 nor WP2 communicate with SAP directly.

## What this WP produces
**Contract C4** — `GET /orders/{order_id}/state` — current order execution state  
**Contract C5** — `POST /odata/v1/ProductionOrders('{order_id}')/Confirm` → forwarded to WP4  
**Contract C10** — MES events webhook to WP5 on order start, confirmation  
See `contracts/interface-contracts.md → C4, C5, C10`.

## What this WP consumes
**Contract C2** — `GET /process-state` from WP2 (SIMATIC) — to display live sensor readings to operator  
**Contract C6** — `GET /odata/v1/ProductionOrders(...)` from WP4 (SAP) — to fetch order data  
**Contract C7** — `GET /odata/v1/Materials(...)` from WP4 (SAP) — to fetch material spec  
**Contract C8** — `POST /odata/v1/GoodsMovements` to WP4 (SAP) — goods receipt post  
See `contracts/interface-contracts.md → C2, C6, C7, C8`.

## Scope

### Must implement
1. **Order management service**:
   - Fetch order from SAP mock (C6) when an order is "released"
   - Maintain local order state in an in-memory store (order_id → state)
   - Expose C4 endpoint

2. **Operator workflow** (state machine per order):
   - `released` → operator sees order, can start
   - `in-progress` → cycle running, live sensor feed visible
   - `confirmed` → operator confirmed completion, quality check logged
   - `closed` → SAP confirmation posted, goods movement posted

3. **SAP integration**:
   - On order start: read material master from SAP (C7), store locally
   - On operator confirmation: POST confirmation to SAP (C5), POST goods movement (C8)

4. **MES event webhook** — on order start and confirmation, POST event to WP5 webhook (C10)

5. **Operator UI** — minimal web page (plain HTML served by FastAPI, or separate Streamlit page):
   - List of released orders (fetched from SAP mock)
   - "Start cycle" button → changes order to in-progress, notifies WP1 control API
   - Live sensor readings panel (polls WP2 /process-state every 5s)
   - "Confirm completion" button + quality check checkbox → triggers SAP write

### Out of scope
- Authentication / user management
- Full Mendix platform replication
- Multiple concurrent orders (single active order per oven)

## Tech stack
- Python 3.11+
- `fastapi` + `uvicorn` — REST API + serve operator UI
- `httpx` — async HTTP client for SAP and SIMATIC calls
- `jinja2` — HTML templating for operator UI (or minimal Streamlit)
- Standard `logging`, `dataclasses`

## Configuration
```
MENDIX_API_PORT=8002
SAP_API_URL=http://localhost:8003
SIMATIC_API_URL=http://localhost:8001
WP1_CONTROL_API_URL=http://localhost:8000
WP5_WEBHOOK_URL=http://localhost:8005/events
PLANT_ID=regensburg
OVEN_ID=oven-01
```

## Folder structure
```
wp3-mendix-mock/
  WP-BRIEF.md
  README.md
  requirements.txt
  .env.example
  src/
    main.py
    order_service.py        Order state machine + in-memory store
    sap_client.py           httpx calls to WP4 (C6, C7, C8)
    simatic_client.py       httpx calls to WP2 (C2)
    wp5_client.py           Webhook push to WP5 (C10)
    api.py                  FastAPI endpoints (C4, C5, operator UI routes)
    models.py               Order, MaterialSpec, ConfirmationRequest dataclasses
    exceptions.py
  templates/
    operator_ui.html        Jinja2 operator interface
  tests/
    test_order_service.py
    test_sap_client.py
    test_api.py
    integration/
      test_full_workflow.py  start order → confirm → verify SAP write
```

## Definition of Done
- [ ] Standard DoD (see SDLC.md Phase 3)
- [ ] Order fetched from WP4 SAP mock on start
- [ ] Order state machine transitions correctly through all states
- [ ] Operator UI renders in browser and all buttons trigger correct state changes
- [ ] SAP confirmation POST and goods movement POST fire on operator confirmation
- [ ] MES event webhook fires on order start and confirmation
- [ ] Integration test: full workflow start → in-progress → confirmed → closed

## Architecture decisions (resolved 2026-06-09)
- **Operator UI**: Jinja2 HTML served by FastAPI. Chosen over Streamlit for zero extra deps and simpler deployment.
- **Cycle start**: WP3 calls WP1 `POST /control/start` when operator clicks Start. WP1 failures are non-fatal (logged as warnings).
- **WP2 -> WP5 push**: WP5 polls WP2 historian (C3) directly. No push webhook from WP2 to WP5. C10 webhook is WP3 -> WP5 only.
- **WP1 port**: `WP1_CONTROL_API_URL=http://localhost:8080` (not 8000 -- Windows excludes port 8000).

## Code review findings (2026-06-10) -- fix before Phase 3 gate

Severity classification follows AI-DEV.md Section 16.

---

### HIGH -- TOCTOU race in `_transition()` (`src/order_service.py:117`)

**Severity:** HIGH (High impact + Med likelihood: concurrent starts both succeed, order starts twice)

**Root cause:** `get()` acquires and releases `_lock` for the dict lookup only. `_transition()` then checks and writes `order.status` **outside** the lock. Two concurrent `POST /orders/{id}/start` requests both call `_transition("released", "in-progress")`. Thread A reads the order (still "released") and the lock is released. Thread B reads the same object (still "released") and the lock is released. Both pass the check. Both write "in-progress". Order is started twice, WP1 called twice, two `cycle_started` C10 events fire.

**Fix applied:** `_transition()` now holds `_lock` for the entire read-check-write sequence. `start()` is rewritten to inline its own locked block (so `target_moisture_ppm` assignment is also atomic -- see MED fix below). `_transition()` continues to serve `confirm()` and `close()`.

---

### HIGH -- Unconditional `svc.close()` when goods movement fails (`src/api.py:235`)

**Severity:** HIGH (High impact: permanent unrecoverable wrong state)

**Root cause:** GM failure was swallowed as a warning and execution fell through to `svc.close()` unconditionally. The order transitioned `confirmed -> closed` with `goods_movement_document=""`. The transition is one-way -- the operator cannot retry and the order is permanently closed without a goods receipt record.

**Fix applied:** `svc.close()` moved inside the GM `try` block -- only runs on success. GM failure raises HTTP 502. `confirm_order()` gains idempotency for the retry case: if the order is already `confirmed` (prior GM failure), `svc.confirm()` is skipped and only the SAP writes + close are retried.

---

### MED -- Ghost `cycle_started` C10 event when WP1 fails (`src/api.py:155`)

**Severity:** MED (Med impact: WP5 expects MQTT data that never arrives; Med likelihood: WP1 not running)

**Root cause:** The C10 `cycle_started` event fired unconditionally after the WP1 call, regardless of whether WP1 succeeded. WP5 receives a start event but no sensor readings follow.

**Fix applied:** `wp1_ok` flag tracks WP1 response. C10 fires only if `wp1_ok=True`. WP1 failure remains non-fatal for the order transition (architecture decision 2026-06-09).

---

### MED -- `target_moisture_ppm` assigned outside lock (`src/api.py:142`)

**Severity:** MED (Med impact: moisture spec threshold bypassed on confirm; Med likelihood: narrow race)

**Root cause:** `svc.start()` released `_lock` after the status transition. The API layer assigned `order.target_moisture_ppm` on the returned object after the lock was gone. A concurrent `confirm_order()` could read `target_moisture_ppm` as `None`, causing `spec_met` to equal `quality_check_passed` regardless of the actual moisture reading.

**Fix applied:** `target_moisture_ppm` passed as a parameter to `svc.start()` and assigned inside the locked block atomically with the status transition.

---

### MED -- Bare `except Exception` in `simatic_proxy()` (`src/api.py:291`)

**Severity:** MED (Med impact: config error masked as 502; Med likelihood: init misconfiguration)

**Root cause:** `_simatic_client` is `None` until `init_app()` is called. Bare `except Exception` converted `AttributeError` (None.get_process_state) into a misleading HTTP 502. See also AI-DEV.md KI-010.

**Fix applied:** Added `_simatic()` guard function (consistent with `_svc()` pattern). Except narrowed to `SimaticClientError`.

---

### LOW -- `_VALID_TRANSITIONS` dead code (`src/order_service.py:13`)

**Severity:** LOW (no runtime effect)

**Root cause:** Dict defined but `_transition()` never consulted it. Each caller passed explicit `expected_from`/`to` values.

**Fix applied:** Deleted the dict.

---

### LOW -- Duplicate SAP fetch in `list_orders()` and `operator_ui()` (`src/api.py:268/299`)

**Severity:** LOW (no correctness impact, extra network call per page load)

**Root cause:** Both endpoints independently called `get_orders(status="RELEASED")` and upserted results. Every browser page load triggered two identical SAP calls.

**Fix applied:** Extracted to `_sync_released_orders()` private helper called from both handlers.

## Session handover notes
Phase 1+2 complete (2026-06-09). Code review done (2026-06-10). 42/42 unit tests passing, 0 warnings, ASCII clean.
Branch: `wp3/mendix-mock`. **Next: apply code review fixes above (HIGH first), re-run tests (expect 42/42+), then Phase 4 seam check.**
Phase 4: run `pytest tests/ -v` (all tests including integration) with WP4 running at localhost:8003.
