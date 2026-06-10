# WP2 — SIMATIC Mock

## Status: NOT STARTED

> **Phase 1 gate (mandatory before writing code):**
> Run the Level 3 harmony check: read `checks/project-patterns.md` and tick off all 12 patterns against your planned structure. Takes ~10 minutes. See `SDLC.md` Phase 1 step 5 and `AI-DEV.md` Section 15.

## Role in the architecture
WP2 simulates the SIMATIC middleware layer. It subscribes to the MQTT sensor stream from WP1, maintains an in-memory historian (time-series buffer), stamps readings with the active production order ID, and exposes two REST endpoints for downstream consumers (WP3, WP5, WP7).

In the real architecture, SIMATIC is the OPC-UA client that subscribes to PLC nodes, writes to a time-series historian, and forwards process state to Mendix. WP2 does the same with MQTT instead of OPC-UA binary.

## What this WP produces
**Contract C2** — `GET /process-state` — current oven status and latest readings  
**Contract C3** — `GET /historian` — time-series query over buffered readings  
See `contracts/interface-contracts.md → C2, C3` for full schemas.

## What this WP consumes
**Contract C1** — MQTT sensor stream from WP1  
See `contracts/interface-contracts.md → C1`.

## Scope

### Must implement
1. **MQTT subscriber** — subscribes to `factory/#`, receives all sensor readings from WP1, parses C1 payload

2. **In-memory historian** — circular buffer of sensor readings per oven:
   - Keyed by `(oven_id, sensor_type)`
   - Configurable max retention (default: 500 readings per channel, ~40 minutes at 5s interval)
   - Thread-safe (subscriber writes, REST endpoints read)

3. **Order context management** — historian stores readings with `order_id` as received from WP1. WP2 tracks the current active order per oven.

4. **REST API** (FastAPI):
   - `GET /process-state` → C2 response: current status, active order, latest readings per sensor type
   - `GET /historian` → C3 response: filtered time-series query
   - `GET /health` → `{ "status": "ok" }`

5. **Status inference** — derive oven status from sensor readings:
   - `idle`: temperature < 40°C and no active order
   - `running`: active order present and temperature rising or at setpoint
   - `complete`: `cycle_complete` signal from MQTT (or moisture below threshold)
   - `fault`: quality flag `Bad` on any sensor for > 30 seconds

### Out of scope
- Actual OPC-UA subscription (WP1 MQTT is the substitute)
- Persistence across restarts (in-memory only)
- Multiple ovens (single oven, single WP2 instance)

## Tech stack
- Python 3.11+
- `paho-mqtt` — MQTT subscriber
- `fastapi` + `uvicorn` — REST API
- `collections.deque` — circular historian buffer
- `threading` — subscriber runs in background thread
- Standard `logging`, `dataclasses`, `datetime`

## Configuration
```
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
SIMATIC_API_PORT=8001
HISTORIAN_MAX_READINGS_PER_CHANNEL=500
PLANT_ID=regensburg
OVEN_ID=oven-01
```

## Folder structure
```
wp2-simatic-mock/
  WP-BRIEF.md
  README.md
  requirements.txt
  .env.example
  src/
    main.py               Entry point
    subscriber.py         MQTT subscriber + message parser
    historian.py          In-memory circular buffer
    status_engine.py      Derive oven status from readings
    api.py                FastAPI endpoints (C2, C3)
    models.py             SensorReading, ProcessState, HistorianResponse dataclasses
    exceptions.py
  tests/
    test_historian.py
    test_status_engine.py
    test_api.py
    integration/
      test_mqtt_to_api.py   Start WP1 + WP2, verify /process-state reflects published readings
```

## Definition of Done
- [ ] Standard DoD (see SDLC.md Phase 3)
- [ ] MQTT subscriber receives WP1 stream and populates historian correctly
- [ ] `GET /process-state` returns C2-compliant response
- [ ] `GET /historian?order_id=...` returns C3-compliant response with correct filtering
- [ ] Status inference transitions correctly (idle → running → complete)
- [ ] Integration test: WP1 publishes → WP2 `/process-state` reflects latest reading within 10s
- [ ] Sample responses documented in README under "Sample output"

## Architecture decisions (resolved 2026-06-09)
- **WP2 -> WP5**: WP5 polls WP2 historian (C3) directly. No push webhook from WP2. MES events (C10) are sent by WP3 only.

## Code review findings (2026-06-10) -- fix before Phase 3 gate

Severity classification follows AI-DEV.md Section 16.

---

### MED -- `/historian` `oven_id` param not in C3 contract (`src/api.py:95`)

**Severity:** MED (Med impact, Low likelihood in single-oven demo -- but contract risk)

**Root cause:**
```python
@app.get("/historian")
def historian_query(
    order_id: str = Query(...),
    oven_id: str = Query("oven-01"),   # not in C3 contract schema
    ...
```
The C3 contract lists `order_id`, `sensor_type`, `from`, `to`, `limit` as query parameters. `oven_id` is not listed. Any caller that follows the contract spec and omits `oven_id` silently receives data for the hardcoded default `oven-01` only. In a multi-oven deployment this would return wrong data without any error signal.

**Fix applied:** Removed `oven_id` from the query parameters. The endpoint now reads `_oven_id` from the module-level global set by `init_app()`, which is populated from the `OVEN_ID` env var. Contract-clean. `init_app()` signature updated to accept `oven_id: str = "oven-01"`.

---

### LOW -- `_utc_now()` dead function (`src/historian.py:15`)

**Severity:** LOW (no runtime effect)

**Root cause:** `_utc_now()` is defined in `historian.py` but the `Historian` class never calls it. The same helper is defined and used in `api.py`. The historian uses `datetime.now(timezone.utc)` directly in `add()` for cycle start tracking, not via the helper.

**Fix applied:** Deleted the dead function from `historian.py`.

---

### LOW -- `OvenNotFoundError` dead import (`src/api.py:11`)

**Severity:** LOW (no runtime effect)

**Root cause:** `from .exceptions import OvenNotFoundError` is present but `OvenNotFoundError` is never raised. The C2 endpoint intentionally returns idle state for unknown ovens rather than raising (comment on line 67: "Return idle state even for unknown ovens (no data yet)"). The import is a leftover from an earlier design that was changed.

**Fix applied:** Removed the dead import.

## Session handover notes
Phase 1+2 complete (2026-06-09). Code review done (2026-06-10). 41/41 unit tests passing, 0 warnings, ASCII clean.
Branch: `wp2/simatic-mock`. **Next: apply 3 code review fixes above, re-run tests, then Phase 4 seam check.**
Phase 4: run `pytest tests/ -v` (all tests including integration) with Mosquitto on localhost:1883 and WP1 running.
