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

- Python 3.11+ (or use root venv)
- Mosquitto broker running: `docker-compose up mosquitto` from project root

## Running locally

```bash
# From project root
cp wp1-sensor-sim/.env.example wp1-sensor-sim/.env
# Edit .env if needed, then:
.venv/Scripts/activate   # Windows
python -m src.main
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `localhost` | MQTT broker hostname |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `SENSOR_PUBLISH_INTERVAL_S` | `5` | Real seconds between readings per sensor |
| `PLANT_ID` | `regensburg` | Plant identifier stamped on every reading |
| `OVEN_ID` | `oven-01` | Oven identifier stamped on every reading |
| `CYCLE_TIME_COMPRESSION` | `60.0` | Simulated seconds per real second (60 = 1h cycle in 1min) |
| `CONTROL_API_PORT` | `8000` | Port for the FastAPI control API |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Control API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/control/start` | Start a drying cycle |
| `POST` | `/control/stop` | Force-stop the active cycle |
| `GET` | `/control/status` | Current simulator state and latest values |
| `GET` | `/health` | Health check |

### Start a cycle

```bash
curl -X POST http://localhost:8000/control/start \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-2026-00042",
    "oven_id": "oven-01",
    "target_temperature_degC": 120.0,
    "target_vacuum_mbar": 5.0,
    "target_moisture_ppm": 300.0,
    "standard_cycle_minutes": 480.0
  }'
```

### Check status

```bash
curl http://localhost:8000/control/status
```

## Running tests

```bash
# From wp1-sensor-sim/ (or use project root venv)
pytest tests/ -v
pytest tests/ --cov=src --cov-report=term-missing   # with coverage
```

Integration tests (require live MQTT broker):
```bash
pytest tests/integration/ --integration
```

## Cycle state machine

```
IDLE → WARMING → DRYING → COMPLETE
         ↑
   (start called)
```

- **IDLE**: ambient readings published, `order_id: null`
- **WARMING**: temperature ramps from ~25°C to setpoint over `warming_duration_minutes` (default 60 simulated min)
- **DRYING**: temperature holds, vacuum drops to setpoint, moisture decays exponentially
- **COMPLETE**: moisture falls below `target_moisture_ppm`

## Sample output

MQTT payload published to `factory/regensburg/oven-01/temperature` during DRYING:

```json
{
  "reading_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp_opc": "2026-06-03T08:32:14.521Z",
  "timestamp_mqtt": "2026-06-03T08:32:14.523Z",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "sensor_type": "temperature",
  "value": 119.847,
  "unit": "degC",
  "quality": "Good",
  "order_id": "ORD-2026-00042"
}
```

MQTT payload published to `factory/regensburg/oven-01/moisture` mid-cycle:

```json
{
  "reading_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "timestamp_opc": "2026-06-03T09:15:44.312Z",
  "timestamp_mqtt": "2026-06-03T09:15:44.314Z",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "sensor_type": "moisture",
  "value": 842.153,
  "unit": "ppm",
  "quality": "Good",
  "order_id": "ORD-2026-00042"
}
```
