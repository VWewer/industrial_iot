# Industrial IoT Architecture – Project Handover
## Context: Siemens Energy Transformers interview prep + portfolio project

> **Version:** v1.2 — June 2026
> **Changes from v1.1:** WP4 implementation complete (Phase 3). Interface contracts v1.1 — full alignment to DOMAIN-MODEL.md (8 contract-level mismatches corrected). Project infrastructure added: docker-compose.yml (Mosquitto + all WP stubs), scripts/healthcheck.sh, scripts/run_validators.sh. WP briefs renamed to WP{n}-BRIEF.md. Seed data: 4 orders, 4 materials. 43/43 tests passing. Next session: WP1 (Sensor Simulator).

---

> ⚠️ **Maintenance instruction for all future sessions:** Sections 0a and 0b below are the at-a-glance project status. Update them at the start or end of every session to reflect the current state. They should always match the body of this document. Do not let them drift.

---

## 0a. Delivery tracker

Each WP progresses through 4 phases. Gate = Definition of Done must pass before the next phase opens. Update status column as work progresses.

| Work package | P1 Design | P2 Build | P3 Test | Gate | P4 Seam | Notes |
|---|---|---|---|---|---|---|
| WP4 — SAP mock | ✅ done | ✅ done | ✅ done | ✅ | ✅ done | 43/43 tests, 18/18 C5-C8 validators |
| WP1 — Sensor sim | ✅ done | ✅ done | ✅ done | ✅ | ✅ done | 42/42 tests, 81% cov, C1 6/6 |
| WP2 — SIMATIC mock | ✅ done | ✅ done | ✅ done | ✅ | ✅ done | 44/44 tests · C2/C3 5/5 validators |
| WP3 — Mendix mock | ✅ done | ✅ done | ✅ done | ✅ | ✅ done | 46/46 tests · C4/C10 4/4 validators |
| WP5 — Snowflake | ✅ done | ✅ done | ✅ done | ✅ | — | 34/34 unit + 1/1 integration. 20 Gold rows, /health OK |
| WP6 — Dashboard | ⬜ after WP5 P3 | — | — | | — | Streamlit in Snowflake |
| WP7 — Cockpit | ⬜ after M2 | — | — | | — | Needs WP2–WP6 |
| WP8 — Agents | stretch | stretch | stretch | | stretch | Stretch goal |

**Gate: Definition of Done (applies to all WPs)**

| Phase | Must pass before next phase |
|---|---|
| P1 Design | Brief reviewed · contracts confirmed · schema locked against DOMAIN-MODEL.md |
| P2 Build | All endpoints/features implemented · seed data loaded · Dockerfile builds |
| P3 Test | Unit + API tests passing · `/health` responds · README sample output written |
| P4 Seam | Contract validator green · consuming WP confirms schema match end-to-end |

**Canonical port assignments** — single source of truth. All `.env.example` files, briefs, and `docker-compose.yml` must match these exactly. Cross-checked by Level 3 harmony check P-13.

| Service | Native port | Docker port | Env var |
|---|---|---|---|
| Mosquitto MQTT broker | 1883 | 1883 | `MQTT_BROKER_PORT` |
| WP1 control API | **8080** (Windows) | 8000 | `CONTROL_API_PORT` |
| WP2 SIMATIC mock | 8001 | 8001 | `SIMATIC_API_PORT` |
| WP3 Mendix mock | 8002 | 8002 | `MENDIX_API_PORT` |
| WP4 SAP mock | 8003 | 8003 | `SAP_API_PORT` |
| WP5 Snowflake layer | 8005 | 8005 | `WP5_API_PORT` |
| WP7 Cockpit | 8501 | 8501 | `COCKPIT_PORT` |

WP6 (Streamlit in Snowflake) runs inside Snowflake -- no local port.
WP1 uses 8080 natively because port 8000 is excluded by Windows (see AI-DEV.md KI-002). Docker is unaffected.

**Milestones**

| Milestone | Condition | Status |
|---|---|---|
| M0 — Infra ready | Contracts v1.1 · docker-compose · scripts · WP4 P3 | ✅ done |
| M1 — First signal | WP1 P4 + WP4 P4 complete | ✅ done (2026-06-04) |
| M2 — Full pipeline | WP2 + WP3 + WP5 P4 complete | 🔵 WP2+WP3 done, WP5 unblocked |
| M3 — Demo ready | WP6 + WP7 P4 · all 4 workflows end-to-end | ⬜ |

---

## 0b. Git workflow status

**✅ Established — 2026-06-03**

- Remote: `https://github.com/VWewer/industrial_iot`
- Default branch: `main` (protected — only merge after Phase 4)
- Current active branches: `wp2/simatic-mock` (P4 complete -- ready to merge), `wp3/mendix-mock` (P4 complete -- ready to merge)
- `main` is up to date: WP1 + WP4 merged (M1 complete, 2026-06-04)

**Ongoing convention:**

- `main` is always demo-ready. Only merge after Phase 4 seam check passes.
- All WP work on `wp{n}/{short-description}` branches.
- Session close = all work committed and pushed to the WP branch.
- Merge to `main` only when Phase 4 is complete for that WP.

**Commit message format:**
```
wp{n}: <imperative verb> <what>
e.g. "wp1: implement MQTT publisher with 3 sensor types"
     "wp4: fix on_event deprecation → lifespan handler"
     "contracts: align C5 endpoint to DOMAIN-MODEL §1.6"
```

---

## 0c. Skills reference

Global skills installed in `~/.claude/skills/` — available in every session.

| Skill | When it activates |
|---|---|
| `python-pro` | Writing any Python module — auto-applied |
| `fastapi-expert` | Any FastAPI WP (WP1–WP4) — auto-applied |
| `api-designer` | Contract questions, new endpoints — auto-applied |
| `sql-pro` | WP5 DDL, Gold layer SQL, Snowflake queries — auto-applied |
| `database-optimizer` | WP5/WP6 query tuning — on request |
| `test-master` | Phase 3 DoD — agent prompts: *"Run test-master review?"* |
| `code-reviewer` | Phase 4 seam check — agent prompts: *"Run /review before merge?"* |
| `devops-engineer` | Dockerfile / docker-compose changes — auto-applied |
| `monitoring-expert` | Logging review — Phase 3 |
| `debugging-wizard` | Any test failure — auto-applied before fixing |
| `architecture-designer` | New ADR, design decisions — on request |
| `secure-code-guardian` | API endpoints, input handling — Phase 4 |
| `the-fool` (`/grill-me`) | Phase 1 kickoff, pre-WP7 — agent prompts to use |

---

## 1. Business problem

Siemens Energy Transformers (Regensburg / Kirchheim) runs transformer drying cycles on fixed time schedules. The actual end-condition — moisture content of the insulation below a threshold — is not measured in real time. Estimated waste: ~15% of cycle time and energy.

The architecture below solves this by:
1. Streaming sensor data (temperature, vacuum, off-gas moisture) from the oven into a central analytics layer
2. Joining it with the production order and material spec from SAP
3. Enabling data-driven cycle-end decisions and retrospective optimisation

The same architecture also solves the broader consolidation problem: replacing a fragile 4-system Power BI pipeline with Snowflake as the single analytical hub (SAP + Mendix/MES + sensor historian all landing in one place).

---

## 2. Architecture model chosen: Model A

**Mendix is the integration hub between SIMATIC and SAP.**
SIMATIC never talks to SAP directly. Mendix owns all SAP connectivity (reads and writes).

```
PLC/Sensors
    ↓ OPC-UA (binary, subscription)
SIMATIC (historian + process context)
    ↓ REST/JSON (process state + order-stamped sensor data)
Mendix (operator UI + SAP connector + Mendix DB)
    ↔ SAP S/4HANA (OData GET / OData POST or BAPI)

SIMATIC ──→ Snowflake  (sensor stream: MQTT → Snowpipe, micro-batch JSON)
Mendix  ──→ Snowflake  (MES events: REST webhook, event-driven JSON)
SAP     ──→ Snowflake  (reference data: OData extract, scheduled batch)

Snowflake (Bronze → Silver → Gold)
    ↓ native query (no connector)
Streamlit in Snowflake (SiS) — analytical dashboard
```

**Reference diagrams:**
- `industrial_iot_architecture_model_a.svg` — real architecture (production reference)
- `industrial_iot_architecture_demo_stack.svg` — portfolio demo stack (WP labels, mock services)

---

## 3. Layer-by-layer reference

### Layer 1: Machine / PLC

**PLC** = Programmable Logic Controller. A ruggedised industrial computer mounted in an electrical cabinet. Runs a continuous control loop (1–100ms): read all sensor inputs → execute logic → write actuator outputs. Physical box with input/output terminals wired directly to sensors and actuators (heaters, pumps, valves).

**Signal chain:**
```
Physical phenomenon (heat)
→ Sensor element (thermocouple, PT100) [millivolt / resistance]
→ Transmitter [small box; converts to 4–20mA scaled to engineering units]
→ PLC analog input card [stores as float in PLC register, e.g. 142.3°C]
→ OPC-UA server [exposes register as a Node in the address space]
```

**Raw voltage is never recorded.** Interpretation happens in the transmitter or PLC input card. Only the engineering value (°C, mbar, kg/h) is stored.

**OPC-UA server** runs on PLC firmware (modern Siemens S7-1500) or on an adjacent gateway box (older S7-300/400). It maintains an address space — a structured map of every variable the PLC exposes. Each Node is a live pointer to a PLC register.

**Value is NOT stored in the Node.** The Node is a window into the current PLC state (updates every scan cycle). Historical accumulation happens in the historian (SIMATIC), not in the PLC.

**Communication modes:**
- **Subscription (push):** OPC-UA client tells server "notify me when value changes beyond X, or every N seconds." Server pushes. Standard for process variables.
- **Poll (pull):** Client asks for current value on demand. Used for one-off reads.

**Data format:** OPC-UA binary (UA Binary). Payload per reading: `NodeID + value + timestamp (server clock) + quality flag (Good / Bad / Uncertain)`.

---

### Layer 2: SIMATIC (middleware)

**Role:** Machine-facing layer. Runs the OPC-UA client. Subscribes to relevant nodes. Stamps every sensor reading with the current production order ID (context from Mendix). Writes to historian.

**Historian:** A time-series database (not a flat file). Append-only log of `timestamp | node_id | value | quality`. Circular storage — operational retention only (hours to days). Answers "what is happening right now" but cannot answer "how did this cycle compare to the last 200."

**Output formats:**
- **MQTT** (to Snowflake via broker): lightweight publish-subscribe protocol. Persistent connection. Sensor data published to topics (e.g. `factory/regensburg/oven-01/temperature`). Snowpipe subscribes via bridge.
- **REST/JSON** (to Mendix): process state, active order context.

**Push or pull:** SIMATIC subscribes to OPC-UA (push from machine). Downstream it pushes via MQTT.

---

### Layer 3: Mendix (application layer)

**What Mendix is:** A low-code application development platform. Used to build web applications (operator-facing, tablet-friendly) without writing traditional code.

**Mendix DB:** A relational database (PostgreSQL underneath) holding:
- Current production order states (synced from SAP)
- Operator actions and confirmations (before they're written back to SAP)
- Application-specific operational data

**Mendix in Model A does three things:**
1. **Operator UI** — start order, confirm operation, log quality check. Event-driven.
2. **SAP integration (downward)** — reads order ID, material master, routing from SAP via OData GET.
3. **SAP integration (upward)** — writes operation confirmations, goods movements, order status back to SAP via OData POST. Synchronous. Event-driven on operator confirmation.

**SIMATIC ↔ Mendix interface:** REST API. SIMATIC exposes process state; Mendix reads it and passes order context back down (which order is active, what the setpoints should be).

---

### Layer 4: SAP S/4HANA

**Role:** System of record. ERP. Source of all reference data and destination for all operational confirmations.

**Key objects relevant to the drying cycle use case:**

| Object | Module | Contains |
|---|---|---|
| Production order | PP | Order number, material, planned qty, scheduled start/end, routing |
| Material master | MM | Transformer type, insulation class, target moisture spec, standard cycle params |
| Routing | PP | Work centres, operations, sequence |
| Equipment master | PM | Physical asset identity, location, maintenance history |
| Functional location | PM | Hierarchy of assets (plant → line → machine) |
| Cost object | CO | Cost collector for the order, basis for settlement |

**Integration interfaces — comparison:**

| Interface | Direction | Sync/Async | Format | When to use |
|---|---|---|---|---|
| OData (SAP Gateway) | Either initiates | Synchronous (req/response) | REST / JSON | Modern S/4HANA preferred. Read and write. |
| IDoc | Either initiates | Asynchronous (fire and forget) | XML | Batch transfers, reliable delivery, SAP-to-SAP or SAP-to-middleware |
| RFC / BAPI | External calls SAP | Synchronous | SAP proprietary | Transactional writes needing immediate confirmation (e.g. post goods movement) |
| BTP Integration Suite | Orchestrated, either | Both | Any | Complex multi-step flows, format mapping, monitoring. Adds governance overhead. |

**SAP → Mendix (downward):** OData GET. Mendix requests order data when order is released in SAP.

**Mendix → SAP (upward):** OData POST / PATCH. Operator confirms operation → Mendix writes confirmation to SAP. Synchronous — needs success/failure response.

**SAP → Snowflake:** Scheduled batch. OData endpoint called by WP5 Python puller. Every 60 seconds for demo. Output: JSON landing in Snowflake Bronze layer.

---

### Layer 5: Snowflake (analytics warehouse)

**Role:** The persistent analytical layer. Receives data from three sources (SIMATIC, Mendix, SAP). Joins them by production order number. Enables cross-cycle analysis impossible from any single source.

**Three-layer model (Bronze → Silver → Gold):**
- **Bronze:** Raw ingestion. Immutable. One table per source stream. Full JSON payload preserved.
- **Silver:** Cleaned, typed, deduplicated. Business keys enforced. Timestamps normalised to UTC.
- **Gold:** Analytical. One row per completed cycle. All sources joined on `order_id`. Business metrics derived (delta_minutes, spec_met, etc.)

**Key Gold table: `gold_cycle_summary`** — see `contracts/snowflake-schema.sql` and `contracts/interface-contracts.md → C12`.

---

## 4. Canonical object reference

See **DOMAIN-MODEL.md** — the authoritative source for all field names, types, enums, and constraints.

| Object | Owner | Key fields |
|---|---|---|
| ProductionOrder | SAP / WP4 | `order_id` (PK), `material_id`, `plant`, `oven_id`, `status` (CREATED/RELEASED/IN_PROGRESS/CONFIRMED/ABORTED/CLOSED) |
| MaterialMaster | SAP / WP4 | `material_id` (PK, format: MAT-{4 digits}), `material_description`, `target_moisture_ppm`, `target_temperature_degC`, `target_vacuum_mbar` |
| SensorReading | WP1 (produced) | `reading_id`, `timestamp_opc`, `timestamp_mqtt`, `plant`, `oven_id`, `sensor_type` (temperature/vacuum/moisture), `value`, `quality` |
| CycleEvent | WP3 (produced) | `event_id`, `event_type` (cycle_started/cycle_confirmed/cycle_aborted/cycle_timeout/sap_confirmation_failed), `order_id`, `oven_id` |
| HistorianSnapshot | WP2 (produced) | `oven_id`, `order_id`, `status` (idle/running/cycle_complete/timeout), `temperature_degC`, `vacuum_mbar`, `moisture_ppm`, `moisture_threshold_met` |
| SAPConfirmation | WP3 → WP4 (C5) | `order_id`, `operation_id`, `confirmed_quantity`, `actual_start`, `actual_end`, `operator_id`, `final_moisture_ppm`, `spec_met` |

---

## 5. Interface contracts summary

See **`contracts/interface-contracts.md` v1.1** — the source of truth for all inter-WP schemas.

**v1.1 corrections applied (June 2026):** 8 contract-level mismatches between original contracts and DOMAIN-MODEL.md were corrected. All WP briefs should reference contracts v1.1.

Key corrections:
- C5 endpoint: `POST /odata/v1/OperationConfirmations` (not `/Confirm`)
- C5 body: `operation_id`, `confirmed_quantity`, `actual_start/end`, `final_moisture_ppm`, `spec_met`
- C7 fields: `material_description`, `target_temperature_degC`, `target_vacuum_mbar`, added `max_cycle_minutes`, `weight_kg`
- C2 endpoint: `GET /process-state/{oven_id}` (oven_id is a path param)
- Sensor types: `temperature`, `vacuum`, `moisture` (3 types — no `heater-power`, no `moisture-offgas`)
- C12 Gold fields: `cycle_start_time`, `cycle_end_time`, `spec_met` (not `moisture_spec_met`)

---

## 6. Production order state machine

```
CREATED → RELEASED → IN_PROGRESS → CONFIRMED → CLOSED
   ↓          ↓           ↓
ABORTED   ABORTED     ABORTED
```

Status enum is uppercase throughout (DOMAIN-MODEL authority). WP3 Mendix mock uses lowercase `in-progress` etc. for its own C4 response — this is a Mendix-internal representation, not the SAP canonical status.

---

## 7. Workpackage status

| WP | Name | Role | Produces | Consumes | Status |
|---|---|---|---|---|---|
| WP1 | Sensor simulator | MQTT sensor stream | C1 | — | NOT STARTED |
| WP2 | SIMATIC mock | Historian + process state | C2, C3 | C1 | NOT STARTED |
| WP3 | Mendix mock | Operator UI + SAP integration hub | C4, C5, C10 | C2, C6, C7, C8 | NOT STARTED |
| WP4 | SAP mock | OData endpoints for orders, materials, GR | C6, C7, C8 (C5 response), C11 | — | **PHASE 3 COMPLETE** |
| WP5 | Snowflake data layer | Bronze→Silver→Gold ingestion + transforms | C12 | C1, C10, C11 | NOT STARTED |
| WP6 | Analytical dashboard (SiS) | Streamlit in Snowflake over Gold layer | UI | WP5 | NOT STARTED |
| WP7 | Unified cockpit | Integrates all four panels | Demo interface | WP2–WP6 | NOT STARTED |
| WP8 | Runtime agents | Anomaly detection, cycle-end prediction | Agent outputs | WP2, WP5 | STRETCH |

### Key design decisions

| Decision | Choice | ADR | Reason |
|---|---|---|---|
| Analytics DB | Real Snowflake | ADR-005 | Account available; enables Snowpipe and SiS |
| Dashboard host | Streamlit in Snowflake (SiS) | ADR-006 | Co-located with data; closes the "single hub" story |
| Mock REST services | FastAPI | ADR-002 | Auto OpenAPI docs, async, type annotations |
| Sensor ingestion | MQTT (Mosquitto broker) | ADR-004 | Authentic to real architecture; fan-out to WP2 and WP5 |
| Scope | Single oven, single plant | ADR-003 | Demonstrates architecture cleanly; multi-oven is horizontal scale |
| Demo cycle timing | 60× compression | ADR-008 | Full cycle demo in ~12–15 real minutes |
| User auth | None | ADR-007 | Panel boundary implies persona; no auth infrastructure needed |
| Agent tooling | Claude Code + Claude chat | — | Structured WP briefs as agent prompts; interface contracts as context |

---

## 8. Repository structure (current)

```
industrial-iot-demo/
  README.md
  CONTRIBUTING.md
  SDLC.md
  AI-DEV.md
  DOMAIN-MODEL.md                   ← canonical authority — start here
  architecture_handover.md          ← this document
  docker-compose.yml                ← NEW v1.2 — starts all services + Mosquitto
  industrial_iot_architecture_model_a.svg
  industrial_iot_architecture_demo_stack.svg

  mosquitto/
    mosquitto.conf                  ← NEW v1.2 — required by docker-compose

  scripts/
    healthcheck.sh                  ← NEW v1.2 — hits all /health endpoints
    run_validators.sh               ← NEW v1.2 — runs contracts/validators/

  contracts/
    interface-contracts.md          ← v1.1 — DOMAIN-MODEL aligned (June 2026)
    mqtt-schema.json
    rest-endpoints.yaml
    snowflake-schema.sql
    seed-data/
      material_masters.json         4 materials (MAT-0001 to MAT-0004)
      production_orders.json        4 orders (CREATED/RELEASED/CONFIRMED/ABORTED)
      historical_cycles.json        20 completed cycles for Gold layer seed
      README.md
    validators/
      validate_c1_mqtt.py
      validate_c10_cycle_event.py
      validate_c12_gold_cycle.py

  docs/
    architecture.md
    decisions.md
    delivery-plan.md

  wp1-sensor-sim/WP1-BRIEF.md       ← renamed from WP-BRIEF.md
  wp2-simatic-mock/WP2-BRIEF.md     ← renamed
  wp3-mendix-mock/WP3-BRIEF.md      ← renamed
  wp4-sap-mock/                     ← IMPLEMENTED
    WP4-BRIEF.md                    ← renamed + updated with session handover
    README.md
    Dockerfile
    requirements.txt
    .env.example
    src/
      __init__.py
      main.py
      data_store.py
      api.py
      models.py
      exceptions.py
    data/
      seed_orders.json
      seed_materials.json
    tests/
      __init__.py
      test_data_store.py
      test_api.py
  wp5-snowflake-layer/WP5-BRIEF.md  ← renamed
  wp6-analytical-dashboard/WP6-BRIEF.md  ← renamed
  wp7-unified-cockpit/WP7-BRIEF.md  ← renamed
  wp8-agent-layer/WP8-BRIEF.md      ← renamed
```

### Where best practices live

| Practice area | Document |
|---|---|
| Canonical object schemas, workflows, data flows, state machine | `DOMAIN-MODEL.md` ← start here |
| Code design standards | `CONTRIBUTING.md` |
| Delivery process (phases, gates, DoD) | `SDLC.md` |
| AI agent methodology | `AI-DEV.md` |
| Interface contracts (field-level schemas) | `contracts/interface-contracts.md` v1.1 |
| Reference data for development and testing | `contracts/seed-data/` |
| Schema validation scripts | `contracts/validators/` |
| Architecture decisions | `docs/decisions.md` (ADRs) |
| Phase map, milestone gates | `docs/delivery-plan.md` |
| Per-WP scope, DoD, and agent prompt context | `wp{n}/WP{n}-BRIEF.md` |

---

## 9. Git workflow

**Branch convention:** `wp{n}/{short-description}` (from CONTRIBUTING.md)

**Flow:**
- `main` is always demo-ready. Only merge when a WP has passed Phase 4 (seam validation).
- All WP work on `wp{n}/` branches.
- Commit frequently within a session. Session close = all work committed.
- Merge to `main` only when Phase 4 seam check is complete for that WP.

**Example:**
```bash
git checkout -b wp4/sap-mock-implementation
# ... work ...
git commit -m "wp4: implement C6 ProductionOrders endpoint"
git commit -m "wp4: implement C5 OperationConfirmations endpoint"
git commit -m "wp4: 43 tests passing, Phase 3 complete"
# After seam validation with WP3:
git checkout main && git merge wp4/sap-mock-implementation
```

---

## 10. Running the stack

**Start infrastructure + WP4:**
```bash
docker-compose up mosquitto wp4
```

**Start everything (once all WPs have Dockerfiles):**
```bash
docker-compose up --build
```

**Health check:**
```bash
./scripts/healthcheck.sh
```

**Run contract validators:**
```bash
./scripts/run_validators.sh
```

**Run WP4 tests:**
```bash
cd wp4-sap-mock && pytest tests/ -v
```

---

## 11. Open items

- [ ] Confirm WP7 analytics panel approach: replicate WP6 queries directly vs iframe/link to SiS app
- [ ] Confirm SiS auto-refresh mechanism: `st.fragment` (Streamlit 1.33+) availability in SiS environment
- [ ] Confirm WP3 operator UI approach: Jinja2 HTML vs Streamlit page
- [ ] Confirm Snowflake staging area naming convention for WP5 Snowpipe setup
- [ ] Agree unified colour palette between WP6 and WP7 before WP7 kickoff
- [ ] Clarify the Accenture thread (Olli vs. Jens Opitz — are these separate routes or the same one?)
- [ ] Migrate WP4 `on_event` deprecation → `lifespan` context manager (cosmetic, non-blocking)
- [ ] Confirm WP5 pull interval for demo (currently 60s default via `SAP_PULL_INTERVAL_S`)

**Resolved from v1.1:**
- ~~MQTT broker setup~~ → `docker-compose.yml` (Mosquitto) — done
- ~~WP-BRIEF.md naming collision~~ → renamed to WP{n}-BRIEF.md — done
- ~~Interface contracts misaligned to DOMAIN-MODEL~~ → contracts v1.1 — done

---

## 12. Next session — recommended starting point

**WP2 and WP3 Phase 4 COMPLETE (2026-06-10).** Both branches ready to merge to main.

**Recommended next: merge WP2 + WP3 to main, then start WP5 (Snowflake data layer)**

**Merge checklist:**
- WP2: `git checkout main && git merge wp2/simatic-mock` -- 44/44 tests, C2/C3 5/5 validators
- WP3: `git checkout main && git merge wp3/mendix-mock` -- 46/46 tests, C4/C10 4/4 validators
- After both merges: M2 milestone complete → WP5 can begin full integration

**WP5 kickoff:**
- Needs Snowflake credentials (account available per ADR-005)
- Reads C1 (MQTT via Mosquitto), C3 (WP2 historian), C10 (WP3 MES events), C11 (WP4 OData)
- Produces C12 (Gold layer `gold_cycle_summary`)
- See `wp5-snowflake-layer/WP5-BRIEF.md`

**Session start template:**
```
"We are continuing the industrial_iot project.
Working directory: C:\Users\vw199\projects\industrial_iot
Read architecture_handover.md first (sections 0a, 0b, 0c), then wp5-snowflake-layer/WP5-BRIEF.md.
Current phase: merge WP2+WP3 to main, then WP5 Phase 1 kickoff."
```

**Milestone target:** M2 complete after WP2+WP3 merge → start WP5 → M2 fully closed when WP5 P4 done.
