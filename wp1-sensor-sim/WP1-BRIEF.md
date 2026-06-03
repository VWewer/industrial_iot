# WP1 — Sensor Simulator

## Status: PHASE 3 COMPLETE — 42/42 tests passing, 81% coverage

## Role in the architecture
WP1 is the bottom of the stack. It simulates a PLC/OPC-UA sensor layer publishing real-time readings for a transformer drying oven. Downstream consumers (WP2, WP5) treat this as if it were a real SIMATIC historian subscribing to real OPC-UA nodes.

## What this WP produces
**Contract C1** — MQTT stream of sensor readings.  
See `contracts/interface-contracts.md → C1` for the full schema.

Topics published:
- `factory/{plant_id}/{oven_id}/temperature`
- `factory/{plant_id}/{oven_id}/vacuum`
- `factory/{plant_id}/{oven_id}/moisture-offgas`
- `factory/{plant_id}/{oven_id}/heater-power`

## What this WP consumes
Nothing upstream. It is the source.

Optional: accepts an order context via a control REST endpoint (see below) so that published readings include the correct `order_id`.

## Scope

### Must implement
1. **Sensor simulation engine** — generates physically plausible readings for a drying cycle:
   - Temperature: ramps from ambient (~25°C) to setpoint (~120°C), then holds
   - Vacuum: drops from atmospheric (1013 mbar) to low (1–2 mbar) as pumps engage
   - Off-gas moisture: starts high (~3000 ppm), decays exponentially as drying proceeds, reaches target (<300 ppm) near cycle end
   - Heater power: high during ramp phase, reduced during hold
   - Add Gaussian noise to all signals (realistic sensor jitter)

2. **MQTT publisher** — publishes each sensor to its topic every `SENSOR_PUBLISH_INTERVAL_S` seconds (default: 5)

3. **Cycle state machine** — manages transitions: `idle → warming → drying → complete`
   - `idle`: publishes ambient readings, `order_id: null`
   - `warming`: temperature ramp phase (~60 min simulated)
   - `drying`: hold phase, moisture decaying (~300 min simulated)
   - `complete`: moisture below target threshold, signals cycle end
   - Cycle duration is configurable (real-time or compressed for demo)

4. **Control API** (FastAPI, `GET/POST /control`):
   - `POST /control/start` — begin a new cycle, accepts `{ "order_id": "...", "oven_id": "..." }`
   - `POST /control/stop` — force stop
   - `GET /control/status` — returns current cycle state and active order_id

5. **Seed data / replay mode** — ability to replay a pre-recorded cycle from a JSON file for deterministic demos

### Out of scope
- Real OPC-UA server (asyncua) — stretch goal for WP8
- Multiple ovens in parallel (single oven only for WP1)
- Fault/alarm simulation (can be added later)

## Tech stack
- Python 3.11+
- `paho-mqtt` — MQTT client
- `fastapi` + `uvicorn` — control API
- `numpy` — signal generation
- Standard `logging`, `os`, `dataclasses`

## Configuration (all via env vars)
```
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
SENSOR_PUBLISH_INTERVAL_S=5
PLANT_ID=regensburg
OVEN_ID=oven-01
CYCLE_TIME_COMPRESSION=1.0      # 1.0 = real time, 60.0 = 1hr in 1min
CONTROL_API_PORT=8000
```

## Folder structure
```
wp1-sensor-sim/
  WP-BRIEF.md
  README.md
  requirements.txt
  .env.example
  src/
    main.py               Entry point — starts MQTT publisher + control API
    simulator.py          Cycle state machine + signal generation
    publisher.py          MQTT publish logic
    control_api.py        FastAPI control endpoints
    models.py             SensorReading dataclass, CycleState enum
    exceptions.py         Custom exceptions
  tests/
    test_simulator.py
    test_publisher.py
    test_control_api.py
    integration/
      test_mqtt_output.py   Validates published payload against C1 schema
  data/
    seed_cycle.json         Pre-recorded cycle for replay mode
```

## Definition of Done
- [x] Standard DoD (see SDLC.md Phase 3)
- [x] Cycle state machine transitions correctly through idle → warming → drying → complete
- [x] Published MQTT payloads validated against C1 schema (jsonschema)
- [x] Off-gas moisture reaches below target threshold by cycle end
- [x] Control API: start/stop/status endpoints respond correctly
- [x] Replay mode produces deterministic output from `seed_cycle.json`
- [x] Sample MQTT output documented in README under "Sample output"

## Open items
- [x] Cycle time compression: confirmed 60× default (ADR-008)
- [x] Mosquitto: confirmed project-level infra (docker-compose up mosquitto)

## Session handover notes
**Session 1 — 2026-06-03 — Phase 1 kickoff through Phase 3 complete**

Implemented all of WP1 from scratch. Key decisions made this session:

- **3 sensor types only** (temperature, vacuum, moisture) — WP1 brief listed 4 but contracts v1.1 explicitly removed `heater-power` and `moisture-offgas`. Implemented per contracts.
- **60× compression default** — confirmed from ADR-008. Warming phase (60 simulated min) = 1 real min. Standard 480-min drying cycle = 8 real min.
- **Signal shapes**: temperature uses exponential approach (tau = warming_duration/3), vacuum uses exponential pulldown (tau = 10 min simulated), moisture uses calibrated exponential decay (k = -ln(target/initial) / standard_cycle_minutes).
- **Thread model**: simulator runs in a daemon thread; on_tick callback fires per publish interval; control API runs in a second daemon thread via uvicorn.
- **Seed data**: `data/seed_cycle.json` generated deterministically (random.seed(42)) — 324 readings covering a full MAT-0001 cycle.

**Test results:** 42/42 passing, 81% coverage. main.py excluded (runtime entry point).

**Next session:** Phase 4 — interface validation. Start Mosquitto (`docker-compose up mosquitto`), start WP1, subscribe to `factory/regensburg/oven-01/#`, trigger a cycle via POST /control/start, capture a payload, run `contracts/validators/validate_c1_mqtt.py` against it.
