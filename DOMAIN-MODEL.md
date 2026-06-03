# DOMAIN-MODEL.md — Industrial IoT Demo: Model A

> **Status:** Draft v1.0 — June 2026  
> **Purpose:** Single reference for all canonical object schemas, user workflows, data flows per workflow, and the production order state machine. Every WP brief and every agent session is written against this document. If there is a conflict between this document and a WP brief or contract, this document wins — update the other artifact.

---

## Table of Contents

1. [Canonical Object Schemas](#1-canonical-object-schemas)
2. [Production Order State Machine](#2-production-order-state-machine)
3. [User Workflows](#3-user-workflows)
4. [Data Flow per Workflow](#4-data-flow-per-workflow)
5. [Sensor Time-Series Model](#5-sensor-time-series-model)
6. [Snowflake Layer Object Map](#6-snowflake-layer-object-map)
7. [Demo Timing Model](#7-demo-timing-model)
8. [Seed Data Specification](#8-seed-data-specification)

---

## 1. Canonical Object Schemas

These are the authoritative field-level definitions for every domain object in the system. All WPs, contracts, and seed data use these field names and types exactly.

---

### 1.1 ProductionOrder

**Owner:** SAP (system of record). Read by Mendix. Stamped onto sensor readings by SIMATIC. Join key in Snowflake Gold.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `order_id` | `string` | PK, format: `ORD-{YYYY}-{5 digits}` | Unique production order identifier. The spine of the entire stack. |
| `material_id` | `string` | FK → MaterialMaster | Which transformer type is being dried |
| `plant` | `string` | enum: `regensburg`, `kirchheim` | Manufacturing plant |
| `oven_id` | `string` | format: `oven-{02d}` | Which physical oven is assigned |
| `planned_start` | `datetime` | ISO 8601, UTC | Scheduled cycle start time |
| `planned_end` | `datetime` | ISO 8601, UTC | Scheduled cycle end time |
| `standard_cycle_minutes` | `integer` | > 0 | Planned duration from material master routing |
| `status` | `string` | enum → see state machine | Current lifecycle state |
| `operator_id` | `string` | nullable | Operator who started the cycle |
| `actual_start` | `datetime` | ISO 8601, UTC, nullable | When cycle actually started |
| `actual_end` | `datetime` | ISO 8601, UTC, nullable | When cycle actually ended (confirmation) |
| `sap_confirmation_number` | `string` | nullable | SAP-assigned confirmation reference |
| `goods_movement_posted` | `boolean` | default: false | Whether goods movement was posted to SAP |
| `created_at` | `datetime` | ISO 8601, UTC | When the order was created in SAP |
| `updated_at` | `datetime` | ISO 8601, UTC | Last modification timestamp |

---

### 1.2 MaterialMaster

**Owner:** SAP (system of record). Read by Mendix and Snowflake Gold layer.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `material_id` | `string` | PK, format: `MAT-{4 digits}` | Unique material identifier |
| `material_description` | `string` | max 100 chars | Human-readable transformer type name |
| `insulation_class` | `string` | enum: `A`, `B`, `F`, `H` | IEC insulation class |
| `target_moisture_ppm` | `integer` | > 0 | Drying endpoint: moisture must be below this value |
| `standard_cycle_minutes` | `integer` | > 0 | Nominal drying duration for this material |
| `max_cycle_minutes` | `integer` | > standard_cycle_minutes | Timeout threshold — cycle flags as overrun beyond this |
| `target_temperature_degC` | `float` | > 0 | Nominal oven temperature setpoint |
| `target_vacuum_mbar` | `float` | > 0 | Nominal vacuum pressure setpoint |
| `weight_kg` | `float` | > 0 | Transformer weight (affects thermal mass) |
| `updated_at` | `datetime` | ISO 8601, UTC | Last SAP update |

**Seed data: 4 material masters** (see Section 8)

---

### 1.3 SensorReading

**Owner:** WP1 (produced). Consumed by WP2 (historian) and WP5 (Bronze ingestion).  
**Transport:** MQTT topic `factory/{plant}/{oven_id}/{sensor_type}`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `reading_id` | `string` | UUID v4 | Unique reading identifier |
| `order_id` | `string` | FK → ProductionOrder, nullable | Stamped by SIMATIC once cycle is active. Null if oven is idle. |
| `oven_id` | `string` | format: `oven-{02d}` | Source oven |
| `plant` | `string` | enum: `regensburg`, `kirchheim` | Source plant |
| `sensor_type` | `string` | enum: `temperature`, `vacuum`, `moisture` | Which physical measurement |
| `value` | `float` | — | Engineering unit value |
| `unit` | `string` | enum: `degC`, `mbar`, `ppm` | Engineering unit |
| `quality` | `string` | enum: `Good`, `Bad`, `Uncertain` | OPC-UA quality flag |
| `timestamp_opc` | `datetime` | ISO 8601, UTC | Timestamp from OPC-UA server (machine clock) |
| `timestamp_mqtt` | `datetime` | ISO 8601, UTC | Timestamp when MQTT message was published |

**Publishing cadence:** Every 5 seconds per sensor (3 sensors → 1 reading/sensor/5s = 36 readings/minute in compressed time)

---

### 1.4 CycleEvent

**Owner:** WP3 (Mendix mock). Produced on operator actions. Consumed by WP5 (Bronze MES ingestion).  
**Transport:** HTTP POST to WP5 webhook `POST /events`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `event_id` | `string` | UUID v4 | Unique event identifier |
| `event_type` | `string` | enum: `cycle_started`, `cycle_confirmed`, `cycle_aborted`, `cycle_timeout`, `sap_confirmation_failed` | What happened |
| `order_id` | `string` | FK → ProductionOrder | Which order this event belongs to |
| `oven_id` | `string` | format: `oven-{02d}` | Which oven |
| `operator_id` | `string` | nullable | Who triggered the event (for operator-initiated events) |
| `timestamp` | `datetime` | ISO 8601, UTC | When the event occurred |
| `payload` | `object` | nullable | Event-specific additional data (see below) |

**Payload by event_type:**

| event_type | payload fields |
|---|---|
| `cycle_started` | `{ "setpoint_temperature_degC": float, "setpoint_vacuum_mbar": float }` |
| `cycle_confirmed` | `{ "sap_confirmation_number": string, "goods_movement_document": string }` |
| `cycle_aborted` | `{ "reason": string }` |
| `cycle_timeout` | `{ "elapsed_minutes": int, "max_cycle_minutes": int }` |
| `sap_confirmation_failed` | `{ "error_code": string, "error_message": string }` |

---

### 1.5 HistorianSnapshot

**Owner:** WP2 (SIMATIC mock). In-memory only. Exposes current oven state via REST.  
**Transport:** REST `GET /process-state/{oven_id}` (Contract C2)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `oven_id` | `string` | format: `oven-{02d}` | Which oven |
| `order_id` | `string` | nullable | Currently active order, null if idle |
| `status` | `string` | enum: `idle`, `running`, `cycle_complete`, `timeout` | Current oven state |
| `temperature_degC` | `float` | nullable | Latest temperature reading |
| `vacuum_mbar` | `float` | nullable | Latest vacuum reading |
| `moisture_ppm` | `float` | nullable | Latest moisture reading |
| `cycle_elapsed_minutes` | `float` | nullable | Time since cycle_started event |
| `moisture_threshold_met` | `boolean` | nullable | Whether moisture < target_moisture_ppm |
| `timestamp` | `datetime` | ISO 8601, UTC | When this snapshot was generated |

---

### 1.6 SAPConfirmation

**Owner:** WP3 (Mendix mock). Written to WP4 (SAP mock) on operator confirmation.  
**Transport:** HTTP POST to WP4 `POST /odata/v1/OperationConfirmations` (Contract C5)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `order_id` | `string` | FK → ProductionOrder | Which order is being confirmed |
| `operation_id` | `string` | format: `{order_id}-OPR-010` | SAP routing operation reference |
| `confirmed_quantity` | `float` | > 0 | Quantity confirmed (units: transformers) |
| `actual_start` | `datetime` | ISO 8601, UTC | Actual cycle start time |
| `actual_end` | `datetime` | ISO 8601, UTC | Actual cycle end time |
| `operator_id` | `string` | — | Confirming operator |
| `final_moisture_ppm` | `float` | — | Final sensor reading at cycle end |
| `spec_met` | `boolean` | — | Whether moisture threshold was met |

---

## 2. Production Order State Machine

The `status` field of `ProductionOrder` follows this state machine. Every WP that reads or writes order status must honour these states and transitions exactly.

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    ▼                                             │
              ┌──────────┐                                        │
              │ RELEASED │  ← Created in SAP, visible in Mendix  │
              └──────────┘                                        │
                    │                                             │
         [WF2: Operator starts cycle]                             │
                    │                                             │
                    ▼                                             │
              ┌─────────┐                                         │
              │ RUNNING │  ← Sensors publishing, order_id stamped │
              └─────────┘                                         │
               │       │                                          │
    [Moisture  │       │ [Elapsed > max_cycle_minutes]            │
     < target] │       │                                          │
               │       ▼                                          │
               │  ┌─────────┐                                     │
               │  │ TIMEOUT │  ← WF5: operator extends or aborts  │
               │  └─────────┘                                     │
               │       │                                          │
               │  [Operator extends]──────────────────────────────┘
               │       │
               │  [Operator aborts]
               │       │
               │       ▼
               │  ┌─────────┐
               │  │ ABORTED │  (terminal)
               │  └─────────┘
               │
    [Moisture < target]
               │
               ▼
        ┌──────────────────┐
        │ THRESHOLD_MET    │  ← Signal shown to operator
        └──────────────────┘
               │
    [WF4: Operator confirms]
               │
               ├──[SAP POST succeeds]──────────────────────────────►
               │                                              ┌──────────┐
               │                                              │ CONFIRMED│ (terminal)
               │                                              └──────────┘
               │
               └──[SAP POST fails]
                          │
                          ▼
                   ┌─────────────────┐
                   │ CONFIRM_FAILED  │  ← WF6: operator retries or escalates
                   └─────────────────┘
                          │
                   [Operator retries]──► back to THRESHOLD_MET
```

**States summary:**

| State | Description | Terminal? |
|---|---|---|
| `RELEASED` | Order exists in SAP, available to shop floor | No |
| `RUNNING` | Cycle active, sensors publishing with order_id stamp | No |
| `TIMEOUT` | Elapsed > max_cycle_minutes, operator decision required | No |
| `THRESHOLD_MET` | Moisture below target, awaiting operator confirmation | No |
| `CONFIRM_FAILED` | SAP confirmation POST failed, retry available | No |
| `CONFIRMED` | SAP confirmation succeeded, goods movement posted | Yes |
| `ABORTED` | Cycle stopped by operator (from RUNNING or TIMEOUT) | Yes |

---

## 3. User Workflows

These are the 6 workflows executable from the WP7 unified cockpit. Each maps to one or more panels and one or more state transitions.

---

### WF1 — Release Production Order
**Panel:** SAP panel (HMI 2 — SAP tab)  
**Persona:** SAP planner / order manager  
**Trigger:** Manual — user selects an order and clicks "Release"  
**Pre-condition:** Order exists in SAP mock with status `CREATED`  
**Post-condition:** Order status = `RELEASED`, visible in Mendix order list

**Steps:**
1. User opens SAP panel
2. Sees list of CREATED orders (from WP4 seed data)
3. Selects an order, reviews material and planned duration
4. Clicks "Release Order"
5. WP4 updates order status to `RELEASED`
6. Mendix panel (HMI 2) order list refreshes — order appears

---

### WF2 — Start Drying Cycle
**Panel:** Mendix panel (HMI 2 — Operator tab)  
**Persona:** Production operator  
**Trigger:** Manual — operator selects released order and clicks "Start Cycle"  
**Pre-condition:** Order status = `RELEASED`, oven status = `idle`  
**Post-condition:** Order status = `RUNNING`, sensor readings begin with `order_id` stamped, machine panel goes live

**Steps:**
1. Operator opens Mendix panel
2. Sees list of RELEASED orders (pulled from WP4 via WP3)
3. Selects order — sees material spec, planned duration, target moisture
4. Clicks "Start Cycle"
5. WP3 sends `cycle_started` CycleEvent to WP5 webhook
6. WP3 notifies WP2: active order_id = this order
7. WP2 begins stamping sensor readings with order_id
8. WP1 sensor simulator begins publishing (if not already running)
9. Machine panel (HMI 1) goes live — gauges update in real time
10. Order status updates to `RUNNING`

---

### WF3 — Monitor Live Cycle
**Panel:** Machine panel (HMI 1)  
**Persona:** Machine operator / shop floor supervisor  
**Trigger:** Automatic — panel is live whenever a cycle is RUNNING  
**Pre-condition:** Order status = `RUNNING`  
**Post-condition:** Read-only — no state changes

**Display:**
- Live temperature gauge (°C) — updates every 5s
- Live vacuum gauge (mbar) — updates every 5s
- Live moisture gauge (ppm) with threshold line — updates every 5s
- Elapsed cycle time vs planned duration
- Order ID and material type
- Status indicator: RUNNING / THRESHOLD MET / TIMEOUT

**No operator actions on this panel — observation only.**

---

### WF4 — Cycle Completion and Confirmation (Happy Path)
**Panel:** Mendix panel (HMI 2 — Operator tab) + machine panel notification  
**Persona:** Production operator  
**Trigger:** Automatic signal when moisture_ppm < target_moisture_ppm  
**Pre-condition:** Order status = `RUNNING`, moisture reading < target  
**Post-condition:** Order status = `CONFIRMED`, goods movement posted, analytics panel updates

**Steps:**
1. WP2 detects moisture_ppm < target_moisture_ppm in latest reading
2. WP2 sets oven status = `cycle_complete`, sets `moisture_threshold_met = true`
3. Machine panel shows "THRESHOLD MET" indicator
4. Mendix panel shows alert: "Cycle complete — confirm to post to SAP"
5. Operator reviews final readings (moisture, duration, peak temp)
6. Operator clicks "Confirm and Post to SAP"
7. WP3 sends `SAPConfirmation` POST to WP4
8. WP4 returns confirmation number + goods movement document number
9. WP3 sends `cycle_confirmed` CycleEvent to WP5 webhook (with SAP confirmation number)
10. WP3 updates order status to `CONFIRMED`
11. WP5 Gold transform runs — new cycle row appears in `gold_cycle_summary`
12. Analytics panel (HMI 3) refreshes — new cycle visible in history table

---

### WF5 — Cycle Timeout (Deviation Handling)
**Panel:** Machine panel (HMI 1) + Mendix panel (HMI 2)  
**Persona:** Production operator / shift supervisor  
**Trigger:** Automatic — elapsed time > `max_cycle_minutes` without threshold met  
**Pre-condition:** Order status = `RUNNING`, elapsed > max_cycle_minutes  
**Post-condition:** Operator decision — either RUNNING (extended) or ABORTED

**Steps:**
1. WP2 detects elapsed_minutes > max_cycle_minutes
2. WP2 sets oven status = `timeout`
3. WP3 sends `cycle_timeout` CycleEvent to WP5
4. Order status updates to `TIMEOUT`
5. Machine panel shows "TIMEOUT" warning with elapsed vs planned duration
6. Mendix panel shows alert with two options: "Extend Cycle" or "Abort Cycle"

**Branch A — Extend:**
7a. Operator clicks "Extend Cycle" (adds N minutes to max_cycle_minutes)
8a. Order status returns to `RUNNING`
9a. Monitoring continues from WF3

**Branch B — Abort:**
7b. Operator clicks "Abort Cycle"
8b. WP3 sends `cycle_aborted` CycleEvent to WP5
9b. Order status = `ABORTED`
10b. Sensors stop being stamped with order_id
11b. Machine panel returns to idle state

---

### WF6 — SAP Confirmation Failure (Error Handling)
**Panel:** Mendix panel (HMI 2)  
**Persona:** Production operator  
**Trigger:** WP4 returns error on SAP confirmation POST  
**Pre-condition:** Order status = `THRESHOLD_MET`, operator has clicked "Confirm"  
**Post-condition:** Operator retry succeeds → `CONFIRMED`, or escalation

**Steps:**
1. Operator clicks "Confirm and Post to SAP" (from WF4, step 6)
2. WP3 sends `SAPConfirmation` POST to WP4
3. WP4 returns HTTP 422 or 500 (order already closed, or system error)
4. WP3 sends `sap_confirmation_failed` CycleEvent to WP5
5. Order status = `CONFIRM_FAILED`
6. Mendix panel shows error: SAP error code + message, with "Retry" button
7. Operator clicks "Retry"
8. Order status returns to `THRESHOLD_MET`
9. Back to WF4 step 6

---

## 4. Data Flow per Workflow

For each workflow, which objects are created/read/updated, across which interfaces, in which order.

---

### WF1 Data Flow — Release Order

```
[SAP Panel / User]
    │
    │  UI click: "Release Order"
    ▼
[WP4 SAP mock]
    PATCH /odata/v1/ProductionOrders/{order_id}
    Body: { "status": "RELEASED" }
    Updates: ProductionOrder.status = RELEASED
    Updates: ProductionOrder.updated_at = now()
    │
    │  WP3 polls WP4 every 30s
    ▼
[WP3 Mendix mock]
    GET /odata/v1/ProductionOrders?$filter=status eq 'RELEASED'
    Reads: ProductionOrder (order_id, material_id, planned_start, planned_end, standard_cycle_minutes, status)
    Reads: MaterialMaster (material_description, target_moisture_ppm, standard_cycle_minutes)
    Updates: WP3 in-memory order list
    │
    │  Mendix panel polls WP3 every 10s
    ▼
[WP7 Mendix Panel]
    Order appears in operator order list
```

**Fields in motion:**

| From | To | Interface | Fields |
|---|---|---|---|
| User | WP4 | HTTP PATCH | `order_id`, `status` |
| WP4 | WP3 | HTTP GET (poll) | `order_id`, `material_id`, `plant`, `oven_id`, `planned_start`, `planned_end`, `standard_cycle_minutes`, `status` |
| WP3 | WP7 | HTTP GET (poll) | same + `material_description`, `target_moisture_ppm` |

---

### WF2 Data Flow — Start Cycle

```
[Mendix Panel / User]
    │
    │  UI click: "Start Cycle"
    ▼
[WP3 Mendix mock]
    1. POST to WP5 webhook: CycleEvent {event_type: cycle_started, order_id, oven_id, timestamp, payload}
    2. PUT to WP2: { active_order_id: order_id }  — stamps the historian
    3. PATCH to WP4: ProductionOrder.status = RUNNING, actual_start = now()
    │
    ├──► [WP5 Bronze — MES webhook]
    │       Writes: bronze_mes_events row
    │
    ├──► [WP2 SIMATIC mock]
    │       Sets: active_order_id for oven-01
    │       Effect: all subsequent SensorReadings stamped with order_id
    │
    └──► [WP4 SAP mock]
            Updates: ProductionOrder.status = RUNNING
            Updates: ProductionOrder.actual_start
```

**Fields in motion:**

| From | To | Interface | Fields |
|---|---|---|---|
| WP3 | WP5 | HTTP POST (webhook) | `event_id`, `event_type`, `order_id`, `oven_id`, `timestamp`, `payload.setpoint_temperature_degC`, `payload.setpoint_vacuum_mbar` |
| WP3 | WP2 | HTTP PUT | `order_id`, `oven_id` |
| WP3 | WP4 | HTTP PATCH | `order_id`, `status`, `actual_start` |

---

### WF3 Data Flow — Monitor Live Cycle

```
[WP1 Sensor Simulator]
    │  Publishes every 5s per sensor
    │  MQTT topic: factory/regensburg/oven-01/{temperature|vacuum|moisture}
    │  Payload: SensorReading (with order_id stamped by WP2 context)
    ▼
[MQTT Broker (Mosquitto)]
    │
    ├──► [WP2 SIMATIC mock — MQTT subscriber]
    │       Updates: HistorianSnapshot (latest values per sensor)
    │       Exposes: GET /process-state/oven-01
    │
    └──► [WP5 Bronze — MQTT subscriber]
            Writes: bronze_sensor_readings row per message

[WP7 Machine Panel]
    │  Polls WP2 every 5s
    │  GET /process-state/oven-01
    │  Reads: HistorianSnapshot
    ▼
    Renders: temperature gauge, vacuum gauge, moisture gauge, elapsed time, status
```

**Fields in motion:**

| From | To | Interface | Fields |
|---|---|---|---|
| WP1 | MQTT broker | MQTT publish | `reading_id`, `order_id`, `oven_id`, `plant`, `sensor_type`, `value`, `unit`, `quality`, `timestamp_opc`, `timestamp_mqtt` |
| MQTT broker | WP2 | MQTT subscribe | same |
| MQTT broker | WP5 | MQTT subscribe | same |
| WP2 | WP7 | HTTP GET | `oven_id`, `order_id`, `status`, `temperature_degC`, `vacuum_mbar`, `moisture_ppm`, `cycle_elapsed_minutes`, `moisture_threshold_met`, `timestamp` |

---

### WF4 Data Flow — Cycle Confirmation (Happy Path)

```
[WP2 SIMATIC mock]
    Detects: moisture_ppm < target_moisture_ppm (from MaterialMaster via WP3 context)
    Sets: HistorianSnapshot.status = cycle_complete
    Sets: HistorianSnapshot.moisture_threshold_met = true
    │
    ▼
[WP7 Machine Panel + Mendix Panel]
    Both poll WP2 — both show THRESHOLD MET signal

[Mendix Panel / User]
    │
    │  UI click: "Confirm and Post to SAP"
    ▼
[WP3 Mendix mock]
    1. POST to WP4: SAPConfirmation
       Body: { order_id, operation_id, confirmed_quantity, actual_start, actual_end,
               operator_id, final_moisture_ppm, spec_met }
       Reads: WP4 returns { sap_confirmation_number, goods_movement_document }
    │
    2. POST to WP5 webhook: CycleEvent { event_type: cycle_confirmed, order_id,
       payload: { sap_confirmation_number, goods_movement_document } }
    │
    3. PATCH to WP4: ProductionOrder.status = CONFIRMED
                     ProductionOrder.actual_end = now()
                     ProductionOrder.sap_confirmation_number = ...
                     ProductionOrder.goods_movement_posted = true
    │
    ├──► [WP4 SAP mock]
    │       Writes: OperationConfirmation record
    │       Writes: GoodsMovement record
    │       Returns: sap_confirmation_number, goods_movement_document
    │
    └──► [WP5 Bronze → Silver → Gold]
            Writes: bronze_mes_events (cycle_confirmed event)
            Trigger: Silver + Gold transforms run
            Writes: gold_cycle_summary row:
                    order_id, material_id, plant, oven_id,
                    cycle_start_time, cycle_end_time,
                    actual_duration_minutes, standard_cycle_minutes, delta_minutes,
                    peak_temperature_degC, min_vacuum_mbar, final_moisture_ppm,
                    target_moisture_ppm, spec_met,
                    sap_confirmation_number, goods_movement_posted

[WP7 Analytics Panel]
    Auto-refresh (30s) → new cycle row appears in cycle overview table
```

---

### WF5 Data Flow — Cycle Timeout

```
[WP2 SIMATIC mock]
    Detects: cycle_elapsed_minutes > MaterialMaster.max_cycle_minutes
    Sets: HistorianSnapshot.status = timeout
    │
    ▼
[WP3 Mendix mock]
    Detects: HistorianSnapshot.status = timeout (via polling WP2)
    POST to WP5 webhook: CycleEvent { event_type: cycle_timeout,
        payload: { elapsed_minutes, max_cycle_minutes } }
    PATCH to WP4: ProductionOrder.status = TIMEOUT

[Mendix Panel / User — Branch A: Extend]
    │  Click: "Extend Cycle" (input: additional minutes)
    ▼
[WP3]
    PUT to WP2: { max_cycle_minutes: new_max }
    PATCH to WP4: ProductionOrder.status = RUNNING

[Mendix Panel / User — Branch B: Abort]
    │  Click: "Abort Cycle"
    ▼
[WP3]
    POST to WP5 webhook: CycleEvent { event_type: cycle_aborted, payload: { reason: "operator_abort" } }
    PUT to WP2: { active_order_id: null }
    PATCH to WP4: ProductionOrder.status = ABORTED
```

---

### WF6 Data Flow — SAP Confirmation Failure

```
[WP3 Mendix mock]
    POST to WP4: SAPConfirmation
    WP4 returns: HTTP 422 { error_code: "ORDER_ALREADY_CLOSED", error_message: "..." }
    │
    WP3:
    POST to WP5 webhook: CycleEvent { event_type: sap_confirmation_failed,
        payload: { error_code, error_message } }
    PATCH to WP4: ProductionOrder.status = CONFIRM_FAILED

[Mendix Panel]
    Shows: error message + "Retry" button

[User clicks Retry]
    PATCH to WP4: ProductionOrder.status = THRESHOLD_MET
    → Returns to WF4 step 6
```

---

## 5. Sensor Time-Series Model

### Physical sensors (3 per oven)

| Sensor | MQTT topic suffix | Unit | Typical range | Behaviour during drying cycle |
|---|---|---|---|---|
| Temperature | `temperature` | `degC` | 80–140°C | Ramps up from ambient, holds at setpoint (~120°C), slight decay at cycle end |
| Vacuum | `vacuum` | `mbar` | 1–50 mbar | Drops rapidly from ambient pressure to setpoint (~5 mbar), holds |
| Moisture (off-gas) | `moisture` | `ppm` | 5000→200 ppm | High at cycle start, exponential decay. Threshold typically 500 ppm. |

### Compressed time model

Real drying cycles run 8–24 hours. For demo purposes:

| Parameter | Value | Configurable via |
|---|---|---|
| Compression factor | 60× (1 real minute = 1 cycle hour) | `CYCLE_COMPRESSION_FACTOR` env var |
| Real demo cycle duration | ~10–15 minutes | Derived from compression + material |
| Sensor publish interval | 5 seconds real time | `SENSOR_PUBLISH_INTERVAL_S` env var |
| Effective sensor resolution | 5 minutes of cycle time per reading | Derived |

### Sensor curve shapes (for WP1 simulator)

**Temperature:** Linear ramp from 20°C to setpoint over first 20% of cycle, then hold ± 2°C noise.

**Vacuum:** Exponential decay from 1013 mbar to setpoint over first 10% of cycle, then hold ± 0.5 mbar noise.

**Moisture:** Exponential decay following:
```
moisture(t) = (initial_ppm - target_ppm) * exp(-k * t) + target_ppm
```
Where `k` is a decay constant derived from `standard_cycle_minutes`. Cycle completes when `moisture(t) < target_moisture_ppm`.

---

## 6. Snowflake Layer Object Map

### Bronze (raw ingestion — immutable)

| Table | Source | Ingestion pattern | Key fields |
|---|---|---|---|
| `bronze_sensor_readings` | WP1 via MQTT | Continuous, per reading | All SensorReading fields + `ingested_at` |
| `bronze_mes_events` | WP3 via webhook | Event-driven | All CycleEvent fields + `ingested_at` |
| `bronze_sap_production_orders` | WP4 via scheduled pull | Every 60s | All ProductionOrder fields + `ingested_at` |
| `bronze_sap_material_master` | WP4 via scheduled pull | Every 60s | All MaterialMaster fields + `ingested_at` |

### Silver (cleaned, typed, deduplicated)

| Table | Derived from | Key transformations |
|---|---|---|
| `silver_sensor_readings` | `bronze_sensor_readings` | Filter `quality = 'Good'`, cast types, deduplicate on `reading_id`, timestamps to UTC |
| `silver_cycle_events` | `bronze_mes_events` | Deduplicate on `event_id`, parse payload JSON, derive `cycle_start_time` and `cycle_end_time` from event pairs |
| `silver_production_orders` | `bronze_sap_production_orders` | Latest version per `order_id` (upsert), cast timestamps |
| `silver_material_master` | `bronze_sap_material_master` | Latest version per `material_id` |

### Gold (analytics-ready — business logic applied)

| Table / View | Derived from | Description |
|---|---|---|
| `gold_cycle_summary` | Silver join (all 4 tables) | One row per completed cycle. Full join by `order_id`. See join query in handover doc. |
| `v_cycle_efficiency` | `gold_cycle_summary` | Aggregated by `material_id`: avg duration, avg delta, avg final moisture, % spec met |
| `v_recent_cycles` | `gold_cycle_summary` | Last 20 completed cycles, ordered by `cycle_end_time` DESC |

### Gold cycle_summary key fields

| Field | Type | Derived from |
|---|---|---|
| `order_id` | string | Join key |
| `material_id` | string | ProductionOrder |
| `material_description` | string | MaterialMaster |
| `plant` | string | ProductionOrder |
| `oven_id` | string | ProductionOrder |
| `cycle_start_time` | datetime | silver_cycle_events (cycle_started event) |
| `cycle_end_time` | datetime | silver_cycle_events (cycle_confirmed event) |
| `actual_duration_minutes` | float | Derived: end - start |
| `standard_cycle_minutes` | integer | MaterialMaster |
| `delta_minutes` | float | Derived: actual - standard (negative = early, positive = late) |
| `peak_temperature_degC` | float | MAX(silver_sensor_readings WHERE sensor_type=temperature) |
| `min_vacuum_mbar` | float | MIN(silver_sensor_readings WHERE sensor_type=vacuum) |
| `final_moisture_ppm` | float | LAST(silver_sensor_readings WHERE sensor_type=moisture) |
| `target_moisture_ppm` | integer | MaterialMaster |
| `spec_met` | boolean | final_moisture_ppm < target_moisture_ppm |
| `sap_confirmation_number` | string | CycleEvent payload |
| `goods_movement_posted` | boolean | ProductionOrder |
| `operator_id` | string | CycleEvent |

---

## 7. Demo Timing Model

For a live demo run of the full workflow (WF1 → WF4):

| Phase | Real time | Cycle time (60× compressed) | What's happening |
|---|---|---|---|
| WF1: Release order | ~30 seconds | — | User clicks release in SAP panel |
| WF2: Start cycle | ~30 seconds | — | Operator clicks start in Mendix panel |
| WF3: Cycle running | ~8–12 minutes | 8–12 hours of cycle time | Gauges live, moisture decaying |
| WF4: Threshold met → Confirm | ~60 seconds | — | Signal fires, operator confirms, SAP posts |
| Analytics refresh | ~30 seconds | — | Gold layer updates, new row appears |
| **Total demo run** | **~12–15 minutes** | — | Full end-to-end |

For a shorter demo (e.g. presenting the system already mid-cycle): pre-seed with active cycle data and join at WF3/WF4 boundary.

---

## 8. Seed Data Specification

### 8.1 Material Masters (4 records)

| material_id | description | insulation_class | target_moisture_ppm | standard_cycle_minutes | max_cycle_minutes | target_temp_degC | target_vacuum_mbar | weight_kg |
|---|---|---|---|---|---|---|---|---|
| `MAT-0001` | Power Transformer 100MVA | H | 300 | 480 | 600 | 130 | 5 | 8500 |
| `MAT-0002` | Distribution Transformer 1MVA | F | 500 | 240 | 300 | 120 | 8 | 850 |
| `MAT-0003` | Instrument Transformer CT 36kV | B | 800 | 120 | 150 | 105 | 12 | 120 |
| `MAT-0004` | Power Transformer 400MVA | H | 200 | 720 | 900 | 135 | 3 | 24000 |

### 8.2 Production Orders (3 records)

| order_id | material_id | plant | oven_id | planned_start | standard_cycle_minutes | status |
|---|---|---|---|---|---|---|
| `ORD-2026-00042` | `MAT-0001` | `regensburg` | `oven-01` | 2026-06-03 06:00 UTC | 480 | `RELEASED` ← active demo order |
| `ORD-2026-00041` | `MAT-0002` | `regensburg` | `oven-01` | 2026-06-02 06:00 UTC | 240 | `CONFIRMED` ← most recent historical |
| `ORD-2026-00039` | `MAT-0003` | `regensburg` | `oven-01` | 2026-05-30 08:00 UTC | 120 | `ABORTED` ← shows deviation case |

### 8.3 Historical Cycles (20 records in gold_cycle_summary)

Distribute across all 4 material types. Target distribution:

| material_id | cycles | spec_met | notes |
|---|---|---|---|
| `MAT-0001` | 7 | 6/7 | One timeout/overrun case |
| `MAT-0002` | 6 | 6/6 | All on spec — reliable short cycle |
| `MAT-0003` | 4 | 3/4 | One slightly over moisture threshold |
| `MAT-0004` | 3 | 2/3 | One significant overrun (heavy unit) |

**Date range:** Last 90 days (March–May 2026), spread roughly weekly.

**Delta distribution:** Mix of early completions (delta -10% to -30%), on-time (delta ±5%), and overruns (delta +10% to +40%). This makes the analytics panel interesting.

**Sensor profile per historical cycle:** Generate 60–100 sensor readings per cycle (one per simulated 5-minute interval of cycle time), covering all 3 sensor types, following the curve shapes in Section 5. Store in `silver_sensor_readings` with correct `order_id` stamps.

---

## Open Items

- [ ] Confirm WP2 moisture threshold detection mechanism: does WP2 read target_moisture_ppm from WP3 context, or is it passed at cycle start?
- [ ] Confirm WP6 deployment: Streamlit in Snowflake (SiS) as agreed — update WP6 brief accordingly
- [ ] Resolve MQTT broker setup: project-level `docker-compose.yml` vs manual Mosquitto — decide before WP1 kickoff
- [ ] Decide WP7 live sensor display: Plotly streaming chart vs gauge components
- [ ] WP5 brief needs updating: DuckDB → real Snowflake (ADR-001 to be superseded)
