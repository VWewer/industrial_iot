# WP5 — Snowflake Data Layer

## Status: NOT STARTED

> **v1.1 — June 2026:** Updated from DuckDB to real Snowflake (ADR-005). Snowpipe for sensor stream ingestion. DuckDB removed from scope.

---

## Role in the architecture

WP5 is the analytical hub. It ingests data from three sources (sensor stream via MQTT, MES events from WP3, reference data from WP4) and transforms it through Bronze → Silver → Gold layers in Snowflake. The Gold layer is the query surface for WP6 (Streamlit in Snowflake dashboard) and WP8 (agents).

The production order number is the join key across all three sources. Every Gold row represents one completed drying cycle with sensor, MES, and SAP data joined.

---

## What this WP produces

**Contract C12** — Gold layer tables queryable in Snowflake

| Table / View | Description |
|---|---|
| `gold_cycle_summary` | One row per completed cycle. All analytics fields. |
| `v_cycle_efficiency` | Aggregated by material_id: avg duration, avg delta, % spec met |
| `v_recent_cycles` | Last 20 completed cycles, ordered by cycle_end_time DESC |

**Full schema:** see `DOMAIN-MODEL.md` Section 6 and `contracts/snowflake-schema.sql`.

**Query API** (minimal FastAPI for WP7 consumption):
```
GET /gold/cycles                    List of recent cycle summaries
GET /gold/cycles/{order_id}         Single cycle detail
GET /gold/efficiency                Material-level efficiency aggregates
GET /health
```

---

## What this WP consumes

**Contract C1 — MQTT sensor stream (from WP1)**
Topic: `factory/regensburg/oven-01/{temperature|vacuum|moisture}`

Payload:
```json
{
  "reading_id": "string (UUID)",
  "order_id": "string | null",
  "oven_id": "string",
  "plant": "string",
  "sensor_type": "temperature | vacuum | moisture",
  "value": "float",
  "unit": "degC | mbar | ppm",
  "quality": "Good | Bad | Uncertain",
  "timestamp_opc": "datetime (ISO 8601 UTC)",
  "timestamp_mqtt": "datetime (ISO 8601 UTC)"
}
```

**Contract C10 — MES events webhook (from WP3)**
Endpoint: `POST /events`

Payload: CycleEvent (see `DOMAIN-MODEL.md` Section 1.4)
```json
{
  "event_id": "string (UUID)",
  "event_type": "cycle_started | cycle_confirmed | cycle_aborted | cycle_timeout | sap_confirmation_failed",
  "order_id": "string",
  "oven_id": "string",
  "operator_id": "string | null",
  "timestamp": "datetime (ISO 8601 UTC)",
  "payload": "object | null"
}
```

**Contracts C6/C7 — SAP reference data pull (from WP4)**
- `GET /odata/v1/ProductionOrders` — all orders
- `GET /odata/v1/MaterialMasters` — all materials

Full schemas: `DOMAIN-MODEL.md` Sections 1.1 and 1.2.

---

## Scope

### Must implement

**1. Bronze ingestion — sensor stream (C1/C9)**
- MQTT subscriber on `factory/#`
- On each message: validate payload, write row to `bronze_sensor_readings`
- Handle `quality = Bad` — write to Bronze regardless (Silver filters)
- Handle malformed payloads: log error, skip, do not crash

**2. Bronze ingestion — MES events (C10)**
- FastAPI endpoint `POST /events`
- Accepts all CycleEvent types
- Writes to `bronze_mes_events`
- Returns 200 on success, 422 on schema validation failure

**3. Bronze ingestion — SAP reference data (C11)**
- Scheduled pull: every 60 seconds (configurable)
- `GET` ProductionOrders and MaterialMasters from WP4
- Upsert to `bronze_sap_production_orders`, `bronze_sap_material_master`
- Full replace per run (SAP data is small, idempotent pull is simpler than delta)

**4. Silver transformations**
- Run on schedule: every 30 seconds (configurable)
- `silver_sensor_readings`: filter quality=Good, cast types, deduplicate on reading_id, timestamps to UTC
- `silver_cycle_events`: deduplicate on event_id, parse payload JSON, derive cycle_start_time and cycle_end_time from event pairs (cycle_started → cycle_confirmed)
- `silver_production_orders`: latest version per order_id (upsert by updated_at)
- `silver_material_master`: latest version per material_id

**5. Gold transformations**
- Run after Silver, same schedule
- Only processes cycles where BOTH cycle_started AND cycle_confirmed events exist
- Full join: silver_sensor_readings + silver_cycle_events + silver_production_orders + silver_material_master
- Computes: peak_temperature_degC, min_vacuum_mbar, final_moisture_ppm, actual_duration_minutes, delta_minutes, spec_met
- Upserts into `gold_cycle_summary`

**6. Seed data loader**
- On startup, if Gold layer is empty: load 20 historical cycles from `contracts/seed-data/`
- Loads into Bronze tables then runs transforms (same pipeline, not a Gold shortcut)
- Idempotent — safe to run multiple times

**7. Query API**
- `GET /gold/cycles` — returns `v_recent_cycles` as JSON list
- `GET /gold/cycles/{order_id}` — returns single gold_cycle_summary row + silver sensor time-series for that order
- `GET /gold/efficiency` — returns `v_cycle_efficiency` as JSON list
- `GET /health` — returns service status + Snowflake connection status

### Out of scope
- dbt (transforms are plain SQL via Snowflake Python connector)
- Kafka (MQTT subscriber sufficient for demo throughput)
- Snowflake time-travel queries (not needed for demo)
- Multi-oven support (single oven-01 in scope — ADR-003)

---

## Tech stack

| Library | Version | Purpose |
|---|---|---|
| `snowflake-connector-python` | `3.7.0` | Snowflake connection, SQL execution, staging |
| `snowflake-ingest` | `2.1.0` | Snowpipe for MQTT Bronze ingestion |
| `paho-mqtt` | `1.6.1` | MQTT subscriber |
| `fastapi` | `0.111.0` | MES webhook + query API |
| `uvicorn` | `0.29.0` | ASGI server |
| `httpx` | `0.27.0` | SAP pull HTTP client |
| `apscheduler` | `3.10.4` | Transform scheduling |
| `pydantic` | `2.7.1` | Payload validation |
| `python-dotenv` | `1.0.1` | Env var loading |

---

## Configuration

```ini
# Snowflake
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=INDUSTRIAL_IOT_DEMO
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=SYSADMIN

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Upstream services
SAP_API_URL=http://localhost:8004

# Timing
SAP_PULL_INTERVAL_S=60
TRANSFORM_INTERVAL_S=30
CYCLE_COMPRESSION_FACTOR=60

# API
WP5_API_PORT=8005

# Seed data
LOAD_SEED_DATA=true
```

---

## Folder structure

```
wp5-snowflake-layer/
  WP-BRIEF.md
  README.md
  requirements.txt
  .env.example
  src/
    main.py                     Entry point — starts all services
    ingestion/
      mqtt_subscriber.py        C1: MQTT → bronze_sensor_readings
      mes_webhook.py            C10: POST /events → bronze_mes_events
      sap_puller.py             C11: WP4 pull → bronze_sap_*
    transforms/
      silver.py                 Bronze → Silver SQL transforms
      gold.py                   Silver → Gold SQL transforms
    scheduler.py                APScheduler: transform + pull intervals
    query_api.py                FastAPI: Gold query endpoints
    snowflake_client.py         Snowflake connection + SQL execution wrapper
    seed_loader.py              Loads contracts/seed-data/ into Bronze pipeline
    models.py                   Pydantic models for API payloads
    exceptions.py               SnowflakeError, MQTTError, IngestionError
  sql/
    init_schema.sql             Creates Bronze/Silver/Gold tables if not exist
    silver_transforms.sql       Silver SQL (parameterised, run by silver.py)
    gold_transforms.sql         Gold SQL (parameterised, run by gold.py)
  tests/
    test_transforms.py          Unit tests for Silver and Gold transform logic
    test_ingestion.py           Unit tests for payload parsing and validation
    test_query_api.py           Unit tests for query API endpoints
    test_seed_loader.py         Unit tests for seed loader
    integration/
      test_end_to_end.py        WP1+WP3+WP4 → WP5 → Gold row appears
  conftest.py                   Fixtures loading from contracts/seed-data/
```

---

## Definition of Done

- [ ] Standard DoD (see SDLC.md Phase 3)
- [ ] Snowflake schema initialised from `contracts/snowflake-schema.sql` on startup
- [ ] MQTT subscriber populates `bronze_sensor_readings` from WP1 stream
- [ ] MES webhook `POST /events` populates `bronze_mes_events` from WP3
- [ ] SAP puller populates `bronze_sap_production_orders` and `bronze_sap_material_master` from WP4
- [ ] Silver transforms run on schedule, produce correctly typed and deduplicated data
- [ ] Gold transforms produce correct `gold_cycle_summary` row for a completed cycle
- [ ] `spec_met` field correctly derived (final_moisture_ppm < target_moisture_ppm)
- [ ] Seed data: 20 historical cycles visible in Gold on first run
- [ ] Query API returns correct Gold data for `/cycles`, `/cycles/{id}`, `/efficiency`
- [ ] Integration test: simulate a cycle end-to-end → verify Gold row appears within 90s

## Open items

- [ ] Confirm Snowflake staging area name convention for Snowpipe (use `WP5_SENSOR_STAGE` or project-level?)
- [ ] Confirm Snowflake warehouse size (XS sufficient for demo throughput?)
- [ ] Decide: WP7 queries Gold via WP5 query API or directly via its own Snowflake connection?

## Session handover notes

> *To be filled by the agent at the end of each session.*
