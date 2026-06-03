# WP2 — SIMATIC Mock

## Status: NOT STARTED

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

## Open items
- [ ] Clarify whether WP2 should push a webhook to WP5 on cycle completion, or WP5 polls

## Session handover notes
> *To be filled by the agent at the end of each session.*
