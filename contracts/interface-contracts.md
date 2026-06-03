# Interface Contracts — Master Reference

This document defines every inter-WP interface in the project. It is the source of truth for field names, types, enum values, and endpoint paths. **DOMAIN-MODEL.md is the authority on canonical object schemas. Any conflict between this document and DOMAIN-MODEL.md must be resolved by updating this document.**

No WP may implement a producer or consumer that diverges from these contracts without first updating this document and flagging all affected WPs.

**Status: REVIEWED v1.1 — aligned to DOMAIN-MODEL.md v1.0 (June 2026)**

---

## Change log

| Date | Change | Affected WPs | Reason |
|---|---|---|---|
| June 2026 | Initial draft | All | — |
| June 2026 | v1.1 — full alignment to DOMAIN-MODEL.md | All | Field name, type, enum, and endpoint mismatches corrected (see review notes below) |

### v1.1 corrections applied

| Contract | Field/item | Old value | New value | Authority |
|---|---|---|---|---|
| C1 | `sensor_type` enum | `temperature`, `vacuum`, `moisture-offgas`, `heater-power` | `temperature`, `vacuum`, `moisture` | DOMAIN-MODEL §1.3 |
| C1 | `timestamp` field | single `timestamp` | `timestamp_opc` + `timestamp_mqtt` | DOMAIN-MODEL §1.3 |
| C1 | Added field | — | `reading_id` (UUID v4) | DOMAIN-MODEL §1.3 |
| C1 | Added field | — | `plant` | DOMAIN-MODEL §1.3 |
| C2 | Endpoint path | `GET /process-state` | `GET /process-state/{oven_id}` | DOMAIN-MODEL §1.5 |
| C2 | Response fields | nested `latest_readings{}` with `moisture_offgas`, `heater_power` | flat fields: `temperature_degC`, `vacuum_mbar`, `moisture_ppm`, `cycle_elapsed_minutes`, `moisture_threshold_met` | DOMAIN-MODEL §1.5 |
| C2 | `status` enum | `idle`, `running`, `complete`, `fault` | `idle`, `running`, `cycle_complete`, `timeout` | DOMAIN-MODEL §1.5 |
| C5 | Endpoint path | `POST /odata/v1/ProductionOrders('{order_id}')/Confirm` | `POST /odata/v1/OperationConfirmations` | DOMAIN-MODEL §1.6 |
| C5 | Request body | `operator_id`, `confirmed_at`, `actual_duration_minutes`, `quality_check_passed`, `goods_movement{}` | `order_id`, `operation_id`, `confirmed_quantity`, `actual_start`, `actual_end`, `operator_id`, `final_moisture_ppm`, `spec_met` | DOMAIN-MODEL §1.6 |
| C6 | Response — added fields | — | `oven_id`, `operator_id`, `actual_start`, `actual_end`, `sap_confirmation_number`, `goods_movement_posted`, `created_at`, `updated_at` | DOMAIN-MODEL §1.1 |
| C6 | Removed field | `routing_id` | — | Not in DOMAIN-MODEL §1.1 canonical schema |
| C7 | Field `description` | `description` | `material_description` | DOMAIN-MODEL §1.2 |
| C7 | Field `max_temperature_degC` | `max_temperature_degC` | `target_temperature_degC` | DOMAIN-MODEL §1.2 |
| C7 | Field `min_vacuum_mbar` | `min_vacuum_mbar` | `target_vacuum_mbar` | DOMAIN-MODEL §1.2 |
| C7 | Added fields | — | `max_cycle_minutes`, `weight_kg`, `updated_at` | DOMAIN-MODEL §1.2 |
| C12 | Field `cycle_start` | `cycle_start` | `cycle_start_time` | DOMAIN-MODEL §6 |
| C12 | Field `cycle_end` | `cycle_end` | `cycle_end_time` | DOMAIN-MODEL §6 |
| C12 | Field `moisture_spec_met` | `moisture_spec_met` | `spec_met` | DOMAIN-MODEL §6 |
| C12 | Added field | — | `oven_id` | DOMAIN-MODEL §6 |
| C12 | Added field | — | `material_description` | DOMAIN-MODEL §6 |
| C12 | Added field | — | `goods_movement_posted` | DOMAIN-MODEL §6 |
| Seed data | `material_id` format | `MAT-TR-440KV-A` style | `MAT-0001` to `MAT-0004` | DOMAIN-MODEL §8.1 |
| Seed data | `order_id` format | `ORD-2024-*` | `ORD-2026-*` | DOMAIN-MODEL §8.2 |
| Seed data | Order `status` casing | `released`, `in-progress` (lowercase) | `RELEASED`, `CONFIRMED`, `ABORTED`, `CREATED` (uppercase) | DOMAIN-MODEL §8.2 |

---

## Contract index

| ID | Interface | Producer | Consumer(s) | Protocol | Format |
|---|---|---|---|---|---|
| C1 | Sensor stream | WP1 | WP2, WP5 | MQTT | JSON |
| C2 | SIMATIC process state | WP2 | WP3, WP7 | REST/JSON | JSON |
| C3 | SIMATIC historian query | WP2 | WP5, WP7 | REST/JSON | JSON |
| C4 | Mendix order state | WP3 | WP7 | REST/JSON | JSON |
| C5 | Mendix → SAP operation confirmation | WP3 | WP4 | REST/JSON (OData-style) | JSON |
| C6 | SAP order data | WP4 | WP3, WP5 | REST/JSON (OData-style) | JSON |
| C7 | SAP material master | WP4 | WP3, WP5 | REST/JSON (OData-style) | JSON |
| C8 | SAP goods receipt post | WP4 | WP3 | REST/JSON (OData-style) | JSON |
| C9 | Bronze ingestion — sensor | WP1→WP5 | WP5 internal | MQTT → Snowflake/Snowpipe | JSON |
| C10 | Bronze ingestion — MES events | WP3→WP5 | WP5 internal | REST webhook | JSON |
| C11 | Bronze ingestion — SAP reference | WP4→WP5 | WP5 internal | Scheduled pull (every 60s) | JSON |
| C12 | Gold layer — cycle summary | WP5 | WP6, WP8 | SQL (Snowflake) | Columnar |

---

## C1 — Sensor stream (MQTT)

**Topic structure:**
```
factory/{plant_id}/{oven_id}/{sensor_type}
```

**Example topics:**
```
factory/regensburg/oven-01/temperature
factory/regensburg/oven-01/vacuum
factory/regensburg/oven-01/moisture
```

**Payload schema:**
```json
{
  "reading_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",  // UUID v4
  "timestamp_opc": "2026-06-03T08:32:14.521Z",            // ISO 8601 UTC — machine clock
  "timestamp_mqtt": "2026-06-03T08:32:14.523Z",           // ISO 8601 UTC — publish time
  "plant": "regensburg",                                   // string, enum: regensburg | kirchheim
  "oven_id": "oven-01",                                    // string, format: oven-{02d}
  "sensor_type": "temperature",                            // enum: temperature | vacuum | moisture
  "value": 142.3,                                          // float, engineering units
  "unit": "degC",                                          // string, see unit table
  "quality": "Good",                                       // enum: Good | Bad | Uncertain
  "order_id": "ORD-2026-00042"                            // string | null (null if no active order)
}
```

**Sensor types and units:**

| sensor_type | unit | typical range | behaviour during drying cycle |
|---|---|---|---|
| `temperature` | `degC` | 20–140 | Ramps from ambient to setpoint (~120°C), holds ±2°C |
| `vacuum` | `mbar` | 1–1013 | Drops from atmospheric to setpoint (~5 mbar), holds |
| `moisture` | `ppm` | 200–5000 | High at start, exponential decay, threshold typically 300–800 ppm |

**Publish frequency:** Every 5 seconds per sensor (configurable via `SENSOR_PUBLISH_INTERVAL_S`).

**MQTT broker:** `localhost:1883` (dev). Configured via `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`.

**QoS:** 1 (at least once delivery).

---

## C2 — SIMATIC process state (REST)

**Base URL:** `http://localhost:8001` (configurable via `SIMATIC_API_URL`)

**Endpoint:** `GET /process-state/{oven_id}`

**Path parameter:** `oven_id` — e.g. `oven-01`

**Response:**
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
  "timestamp": "2026-06-03T08:32:14Z"
}
```

**Field definitions:**

| Field | Type | Description |
|---|---|---|
| `oven_id` | string | Which oven |
| `order_id` | string \| null | Currently active order. Null if idle. |
| `status` | string | enum: `idle` \| `running` \| `cycle_complete` \| `timeout` |
| `temperature_degC` | float \| null | Latest temperature reading |
| `vacuum_mbar` | float \| null | Latest vacuum reading |
| `moisture_ppm` | float \| null | Latest moisture reading |
| `cycle_elapsed_minutes` | float \| null | Minutes since cycle start |
| `moisture_threshold_met` | boolean \| null | Whether moisture_ppm < target_moisture_ppm |
| `timestamp` | datetime | When this snapshot was generated |

---

## C3 — SIMATIC historian query (REST)

**Endpoint:** `GET /historian`

**Query parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `order_id` | string | yes | Filter by production order |
| `sensor_type` | string | no | Filter by sensor type (temperature \| vacuum \| moisture) |
| `from` | ISO 8601 | no | Start of time range |
| `to` | ISO 8601 | no | End of time range |
| `limit` | int | no | Max rows (default 1000) |

**Response:**
```json
{
  "order_id": "ORD-2026-00042",
  "count": 144,
  "readings": [
    {
      "reading_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "timestamp_opc": "2026-06-03T07:00:00Z",
      "sensor_type": "temperature",
      "value": 95.1,
      "unit": "degC",
      "quality": "Good"
    }
  ]
}
```

---

## C4 — Mendix order state (REST)

**Base URL:** `http://localhost:8002` (configurable via `MENDIX_API_URL`)

**Endpoint:** `GET /orders/{order_id}/state`

**Response:**
```json
{
  "order_id": "ORD-2026-00042",
  "status": "in-progress",
  "operator_id": "OP-007",
  "cycle_confirmed_at": null,
  "quality_check_passed": null
}
```

**`status` enum:** `released` | `in-progress` | `confirmed` | `closed`

---

## C5 — Mendix → SAP operation confirmation (OData-style REST)

**Endpoint on SAP mock (WP4):** `POST /odata/v1/OperationConfirmations`

**Request body** (SAPConfirmation schema — see DOMAIN-MODEL §1.6):
```json
{
  "order_id": "ORD-2026-00042",
  "operation_id": "ORD-2026-00042-OPR-010",
  "confirmed_quantity": 1.0,
  "actual_start": "2026-06-03T06:05:00Z",
  "actual_end": "2026-06-03T13:58:00Z",
  "operator_id": "OP-007",
  "final_moisture_ppm": 287.4,
  "spec_met": true
}
```

**Response:**
```json
{
  "order_id": "ORD-2026-00042",
  "sap_confirmation_number": "CONF-2026-00891",
  "status": "CONFIRMED",
  "posted_at": "2026-06-03T14:00:03Z"
}
```

---

## C6 — SAP order data (OData-style REST)

**Base URL:** `http://localhost:8003` (configurable via `SAP_API_URL`)

**Endpoints:**
- `GET /odata/v1/ProductionOrders` — list all orders (supports `?status=RELEASED&plant=regensburg`)
- `GET /odata/v1/ProductionOrders('{order_id}')` — single order

**Single order response** (full ProductionOrder schema — see DOMAIN-MODEL §1.1):
```json
{
  "order_id": "ORD-2026-00042",
  "material_id": "MAT-0001",
  "plant": "regensburg",
  "oven_id": "oven-01",
  "planned_start": "2026-06-03T06:00:00Z",
  "planned_end": "2026-06-03T14:00:00Z",
  "standard_cycle_minutes": 480,
  "status": "RELEASED",
  "operator_id": null,
  "actual_start": null,
  "actual_end": null,
  "sap_confirmation_number": null,
  "goods_movement_posted": false,
  "created_at": "2026-06-02T14:30:00Z",
  "updated_at": "2026-06-02T14:30:00Z"
}
```

**List response:**
```json
{
  "count": 4,
  "value": [ /* array of order objects */ ]
}
```

---

## C7 — SAP material master (OData-style REST)

**Endpoint:** `GET /odata/v1/Materials('{material_id}')`

**Response** (full MaterialMaster schema — see DOMAIN-MODEL §1.2):
```json
{
  "material_id": "MAT-0001",
  "material_description": "Power Transformer 100MVA",
  "insulation_class": "H",
  "target_moisture_ppm": 300,
  "standard_cycle_minutes": 480,
  "max_cycle_minutes": 600,
  "target_temperature_degC": 130.0,
  "target_vacuum_mbar": 5.0,
  "weight_kg": 8500.0,
  "updated_at": "2026-06-01T00:00:00Z"
}
```

---

## C8 — SAP goods receipt post (OData-style REST)

**Endpoint:** `POST /odata/v1/GoodsMovements`

**Request body:**
```json
{
  "order_id": "ORD-2026-00042",
  "material_id": "MAT-0001",
  "movement_type": "GR_PRODUCTION",
  "quantity": 1,
  "unit": "EA",
  "posting_date": "2026-06-03",
  "storage_location": "WH-01"
}
```

**Response:**
```json
{
  "document_number": "GR-2026-003891",
  "posted_at": "2026-06-03T14:00:05Z",
  "status": "posted"
}
```

---

## C10 — MES events webhook (WP3 → WP5)

**Endpoint on WP5:** `POST /events`

**Payload** (CycleEvent schema — see DOMAIN-MODEL §1.4):
```json
{
  "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "event_type": "cycle_started",
  "order_id": "ORD-2026-00042",
  "oven_id": "oven-01",
  "operator_id": "OP-007",
  "timestamp": "2026-06-03T06:05:00Z",
  "payload": {
    "setpoint_temperature_degC": 130.0,
    "setpoint_vacuum_mbar": 5.0
  }
}
```

**`event_type` enum:** `cycle_started` | `cycle_confirmed` | `cycle_aborted` | `cycle_timeout` | `sap_confirmation_failed`

**Payload by event_type:**

| event_type | payload fields |
|---|---|
| `cycle_started` | `{ "setpoint_temperature_degC": float, "setpoint_vacuum_mbar": float }` |
| `cycle_confirmed` | `{ "sap_confirmation_number": string, "goods_movement_document": string }` |
| `cycle_aborted` | `{ "reason": string }` |
| `cycle_timeout` | `{ "elapsed_minutes": int, "max_cycle_minutes": int }` |
| `sap_confirmation_failed` | `{ "error_code": string, "error_message": string }` |

**Response:** `{ "status": "accepted", "event_id": "..." }`

---

## C11 — SAP reference data batch pull (WP5 → WP4)

**Pull schedule:** Every 60 seconds (configurable via `SAP_PULL_INTERVAL_S`).

**Endpoints polled by WP5:**
- `GET /odata/v1/ProductionOrders` — all orders (WP5 filters and upserts to Bronze)
- `GET /odata/v1/Materials('{material_id}')` — one request per known material
- `GET /odata/v1/GoodsMovements` — all posted movements

**WP5 writes results to:** `bronze_sap_production_orders`, `bronze_sap_material_master`, `bronze_sap_goods_movements`

---

## C12 — Gold layer schema (Snowflake)

See `contracts/snowflake-schema.sql` for full DDL. The canonical field list is defined in DOMAIN-MODEL.md §6.

**Key Gold table: `gold_cycle_summary`**

| Column | Type | Description |
|---|---|---|
| `order_id` | VARCHAR | Production order — the join spine |
| `material_id` | VARCHAR | Transformer type |
| `material_description` | VARCHAR | Human-readable transformer name |
| `plant` | VARCHAR | Plant identifier |
| `oven_id` | VARCHAR | Which oven |
| `cycle_start_time` | TIMESTAMP | Actual cycle start (from cycle_started event) |
| `cycle_end_time` | TIMESTAMP | Actual cycle end (from cycle_confirmed event) |
| `actual_duration_minutes` | FLOAT | Derived: end − start |
| `standard_cycle_minutes` | INT | From MaterialMaster |
| `delta_minutes` | FLOAT | actual − standard (negative = faster) |
| `peak_temperature_degC` | FLOAT | MAX sensor reading during cycle |
| `min_vacuum_mbar` | FLOAT | MIN sensor reading during cycle |
| `final_moisture_ppm` | FLOAT | LAST moisture reading at cycle end |
| `target_moisture_ppm` | INT | Spec from MaterialMaster |
| `spec_met` | BOOLEAN | final_moisture_ppm < target_moisture_ppm |
| `quality_check_passed` | BOOLEAN | Operator quality confirmation |
| `operator_id` | VARCHAR | From CycleEvent |
| `sap_confirmation_number` | VARCHAR | SAP confirmation reference |
| `goods_movement_posted` | BOOLEAN | Whether GR was posted to SAP |
