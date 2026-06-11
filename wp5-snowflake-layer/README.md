# WP5 -- Snowflake Data Layer

Ingests industrial IoT data into Snowflake Bronze/Silver/Gold layers and exposes a Gold query API.

## Architecture

```
WP1 (MQTT sensor stream) ─────────────────────────────┐
WP3 (MES events webhook) ──── Bronze ─ Silver ─ Gold ──┼─► WP6 (SiS dashboard)
WP4 (SAP reference pull) ─────────────────────────────┘    WP7 (cockpit agent)
```

Port: **8005** (`WP5_API_PORT`)

## Quick start

```powershell
# From wp5-snowflake-layer/
cd wp5-snowflake-layer
copy .env.example .env    # then fill in Snowflake credentials
..\.venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SNOWFLAKE_ACCOUNT` | (required) | Snowflake account identifier |
| `SNOWFLAKE_USER` | (required) | Snowflake user |
| `SNOWFLAKE_PASSWORD` | (required) | Snowflake password |
| `SNOWFLAKE_DATABASE` | `INDUSTRIAL_IOT_DEMO` | Target database |
| `SNOWFLAKE_SCHEMA` | `PUBLIC` | Target schema |
| `SNOWFLAKE_WAREHOUSE` | `COMPUTE_WH` | XS warehouse |
| `SNOWFLAKE_ROLE` | `SYSADMIN` | Execution role |
| `MQTT_BROKER_HOST` | `localhost` | Mosquitto broker host |
| `MQTT_BROKER_PORT` | `1883` | Mosquitto broker port |
| `SAP_API_URL` | `http://localhost:8003` | WP4 SAP mock URL |
| `SAP_PULL_INTERVAL_S` | `60` | SAP reference data pull interval |
| `TRANSFORM_INTERVAL_S` | `30` | Silver/Gold transform interval |
| `WP5_API_PORT` | `8005` | FastAPI port |
| `LOAD_SEED_DATA` | `true` | Load 20 historical cycles on first startup |

## API endpoints

```
GET  /health                      Service + Snowflake connection status
POST /events                      MES cycle event webhook (C10 contract)
GET  /gold/cycles                 Last 50 completed cycles (v_recent_cycles)
GET  /gold/cycles/{order_id}      Single cycle + sensor time-series
GET  /gold/efficiency             Per-material efficiency aggregates (v_cycle_efficiency)
```

### Sample output

```json
GET /health
{"status": "ok", "service": "wp5-snowflake-layer", "snowflake_connected": true}

GET /gold/cycles
[
  {
    "order_id": "ORD-2026-00041",
    "material_id": "MAT-0002",
    "material_description": "Distribution Transformer 1MVA",
    "plant": "regensburg",
    "oven_id": "oven-01",
    "cycle_start_time": "2026-06-02T06:05:00",
    "cycle_end_time": "2026-06-02T09:48:00",
    "actual_duration_minutes": 223.0,
    "standard_cycle_minutes": 240,
    "delta_minutes": -17.0,
    "peak_temperature_degC": 121.4,
    "min_vacuum_mbar": 7.8,
    "final_moisture_ppm": 412.0,
    "target_moisture_ppm": 500.0,
    "spec_met": true,
    "goods_movement_posted": true
  }
]
```

## Running tests

```powershell
# Unit tests only (no Snowflake required)
..\.venv\Scripts\pytest.exe tests/ -m "not integration" -v

# Integration tests (require Snowflake + MQTT)
..\.venv\Scripts\pytest.exe tests/integration/ -m integration -v
```

## Data flow

1. **Bronze ingestion** (raw, no transformation)
   - `bronze_sensor_readings` -- MQTT messages from WP1 via `factory/#`
   - `bronze_mes_events` -- cycle events POSTed by WP3 to `POST /events`
   - `bronze_sap_production_orders` / `bronze_sap_material_master` -- WP4 pull every 60s

2. **Silver transforms** (every 30s, scheduled)
   - Filter sensor readings to `quality = Good`
   - Deduplicate on `reading_id` / `event_id`
   - Extract `quality_check_passed`, `sap_confirmation_number` from MES event JSON

3. **Gold transforms** (every 30s, after Silver)
   - JOIN: cycle events + sensor aggregates + production order + material master
   - Computes: `actual_duration_minutes`, `delta_minutes`, `spec_met`
   - Only processes cycles with BOTH `cycle_started` AND `cycle_confirmed` events

4. **Seed data** (on first startup when Gold is empty)
   - Loads 20 historical cycles via the full Bronze pipeline (not a Gold shortcut)
