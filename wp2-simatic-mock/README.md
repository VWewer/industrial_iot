# WP2 -- SIMATIC Mock

Simulates the SIMATIC middleware layer. Subscribes to the WP1 MQTT sensor stream, maintains a thread-safe in-memory historian, and exposes REST endpoints (C2, C3) for downstream consumers (WP3, WP5, WP7).

## Run

```powershell
cd wp2-simatic-mock
copy .env.example .env          # edit as needed
..\\.venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

API available at `http://localhost:8001`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `localhost` | Mosquitto broker hostname |
| `MQTT_BROKER_PORT` | `1883` | Mosquitto broker port |
| `SIMATIC_API_PORT` | `8001` | FastAPI listen port |
| `HISTORIAN_MAX_READINGS_PER_CHANNEL` | `500` | Circular buffer depth per (oven, sensor) pair |
| `MOISTURE_THRESHOLD_PPM` | `500` | Moisture below which status becomes `cycle_complete` |
| `MAX_CYCLE_MINUTES` | `600` | Elapsed minutes beyond which status becomes `timeout` |
| `PLANT_ID` | `regensburg` | Plant identifier |
| `OVEN_ID` | `oven-01` | Oven identifier |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Tests

```powershell
cd wp2-simatic-mock
..\\.venv\Scripts\pytest.exe tests/ -v -m "not integration"
# with live MQTT broker:
..\\.venv\Scripts\pytest.exe tests/ -v
```

## Sample output

`GET /process-state/oven-01`
```json
{
  "oven_id": "oven-01",
  "order_id": "ORD-2026-00042",
  "status": "running",
  "temperature_degC": 118.7,
  "vacuum_mbar": 4.9,
  "moisture_ppm": 1240.0,
  "cycle_elapsed_minutes": 47.3,
  "moisture_threshold_met": false,
  "timestamp": "2026-06-09T10:32:14.521Z"
}
```

`GET /historian?order_id=ORD-2026-00042&sensor_type=temperature&limit=3`
```json
{
  "order_id": "ORD-2026-00042",
  "count": 3,
  "readings": [
    {
      "reading_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "timestamp_opc": "2026-06-10T08:00:00.000Z",
      "sensor_type": "temperature",
      "value": 80.0,
      "unit": "degC",
      "quality": "Good"
    },
    {
      "reading_id": "b2c3d4e5-f6a7-8901-bcde-f01234567891",
      "timestamp_opc": "2026-06-10T08:00:30.000Z",
      "sensor_type": "temperature",
      "value": 95.0,
      "unit": "degC",
      "quality": "Good"
    },
    {
      "reading_id": "c3d4e5f6-a7b8-9012-cdef-012345678902",
      "timestamp_opc": "2026-06-10T08:01:00.000Z",
      "sensor_type": "temperature",
      "value": 110.0,
      "unit": "degC",
      "quality": "Good"
    }
  ]
}
```

Phase 4 seam check: `5/5 C2/C3 contract checks` passed 2026-06-10.
Run: `.venv/Scripts/python contracts/validators/run_wp2_phase4_check.py`
