# WP1 — Sensor Simulator

Simulates a PLC/OPC-UA sensor layer for a transformer drying oven. Publishes real-time temperature, vacuum, and moisture readings to MQTT (Contract C1). Exposes a REST control API to start/stop cycles and query simulator state.

## What it produces

**Contract C1** — MQTT stream on topics:
```
factory/{plant_id}/{oven_id}/temperature
factory/{plant_id}/{oven_id}/vacuum
factory/{plant_id}/{oven_id}/moisture
```

One reading per sensor every `SENSOR_PUBLISH_INTERVAL_S` seconds (default 5s real time).

## Prerequisites

- Python 3.11+ (use the root `.venv` — `C:\Users\vw199\projects\industrial_iot\.venv`)
- A running Mosquitto MQTT broker on port 1883

### Starting Mosquitto

**Windows (recommended — native service):**
```powershell
# Install once via winget (adds Mosquitto as a Windows Service)
winget install EclipseFoundation.Mosquitto

# Service starts automatically on install and on reboot.
# Confirm it is listening:
netstat -ano | Select-String ":1883"
```

**Docker (if available):**
```bash
docker compose up mosquitto
```

## Running locally

```powershell
# From project root — activate venv
.venv\Scripts\Activate.ps1

# From wp1-sensor-sim/
# NOTE: port 8000 is reserved by Windows on many machines.
# Use 8080 (or any free port) for the control API.
$env:CONTROL_API_PORT = "8080"
python -m src.main
```

All other settings use defaults (`localhost:1883`, plant `regensburg`, oven `oven-01`, 60x compression).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `localhost` | MQTT broker hostname |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `SENSOR_PUBLISH_INTERVAL_S` | `5` | Real seconds between readings per sensor |
| `PLANT_ID` | `regensburg` | Plant identifier stamped on every reading |
| `OVEN_ID` | `oven-01` | Oven identifier stamped on every reading |
| `CYCLE_TIME_COMPRESSION` | `60.0` | Simulated seconds per real second (60 = 1 h cycle in 1 min) |
| `CONTROL_API_PORT` | `8000` | Port for the FastAPI control API (use 8080 on Windows) |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Control API

Base URL: `http://localhost:{CONTROL_API_PORT}`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/control/start` | Start a drying cycle |
| `POST` | `/control/stop` | Force-stop the active cycle |
| `GET` | `/control/status` | Current simulator state and latest values |
| `GET` | `/health` | Health check |

### Start a cycle

```bash
curl -X POST http://localhost:8080/control/start \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-2026-00001",
    "oven_id": "oven-01"
  }'
```

Response:
```json
{"status": "started", "order_id": "ORD-2026-00001"}
```

### Check status

```bash
curl http://localhost:8080/control/status
```

Response (mid-cycle):
```json
{
  "state": "drying",
  "order_id": "ORD-2026-00001",
  "simulated_elapsed_minutes": 220.0,
  "temperature_degC": 119.97,
  "vacuum_mbar": 5.02,
  "moisture_ppm": 1483.6
}
```

## Running tests

```powershell
# From wp1-sensor-sim/
pytest tests/ -v
pytest tests/ --cov=src --cov-report=term-missing   # with coverage

# Integration tests (require live Mosquitto on localhost:1883):
pytest tests/integration/ -m integration
```

**Expected result:** 43 passed, 0 warnings.

## Phase 4 seam check (C1 validator)

Captures live MQTT output and validates every payload against Contract C1:

```powershell
# Add Mosquitto CLI to PATH (Windows)
$env:PATH = $env:PATH + ";C:\Program Files\mosquitto"

# 1. Start WP1 (see "Running locally" above)

# 2. Capture 6 messages (2 publish intervals x 3 sensors)
mosquitto_sub -h localhost -t "factory/regensburg/oven-01/#" -C 6 -v > captured.txt

# 3. Trigger a cycle in a separate terminal
curl -X POST http://localhost:8080/control/start -H "Content-Type: application/json" -d '{"order_id":"ORD-2026-00001","oven_id":"oven-01"}'

# 4. Validate all captured payloads
python ..\contracts\validators\run_phase4_check.py captured.txt
```

**Phase 4 result (2026-06-03):** 6/6 PASS — all three sensor types, both publish intervals.

## Cycle state machine

```
IDLE -> WARMING -> DRYING -> COMPLETE
         |
   (start called)
```

- **IDLE**: ambient readings published, `order_id: null`
- **WARMING**: temperature ramps from ~25 degC to setpoint over `warming_duration_minutes` (default 60 simulated min)
- **DRYING**: temperature holds, vacuum drops to setpoint, moisture decays exponentially
- **COMPLETE**: moisture falls below `target_moisture_ppm`

## Sample MQTT output

Published to `factory/regensburg/oven-01/temperature` during DRYING:

```json
{
  "reading_id": "5f11a6e1-d279-4ffc-9fdf-807ce3485f97",
  "timestamp_opc": "2026-06-03T15:42:30.077Z",
  "timestamp_mqtt": "2026-06-03T15:42:30.077Z",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "sensor_type": "temperature",
  "value": 46.553,
  "unit": "degC",
  "quality": "Good",
  "order_id": "ORD-2026-00001"
}
```

Published to `factory/regensburg/oven-01/moisture` at start of cycle:

```json
{
  "reading_id": "af9a3ddc-19db-4ab1-a4e2-378cf996a886",
  "timestamp_opc": "2026-06-03T15:42:30.077Z",
  "timestamp_mqtt": "2026-06-03T15:42:30.078Z",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "sensor_type": "moisture",
  "value": 4999.041,
  "unit": "ppm",
  "quality": "Good",
  "order_id": "ORD-2026-00001"
}
```

All timestamps are ISO 8601 UTC with millisecond precision (e.g. `2026-06-03T15:42:30.077Z`).
