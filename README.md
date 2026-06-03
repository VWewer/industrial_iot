# Industrial IoT Demo — Model A

## What this is

A portfolio project demonstrating end-to-end delivery of an industrial IoT analytics architecture — from PLC sensor simulation through to an analytical dashboard — across a realistic multi-system stack with authentic connectors.

**Business problem:** Siemens Energy Transformers runs transformer drying cycles on fixed time schedules. Actual cycle-end condition (insulation moisture below threshold) is not measured in real time. Estimated waste: ~15% of cycle time and energy. This architecture solves that by streaming sensor data into a central analytics layer and joining it with production order and material spec data from SAP.

**Secondary problem:** Replacing a fragile multi-system Power BI pipeline with Snowflake as the single analytical hub (SAP + Mendix/MES + sensor historian all landing in one place).

---

## Architecture — Model A

```
PLC/Sensors
    ↓ OPC-UA (binary, subscription)
SIMATIC (historian + process context)          [WP2]
    ↓ REST/JSON (process state + order-stamped sensor data)
Mendix (operator UI + SAP connector)          [WP3]
    ↔ SAP S/4HANA (OData GET / OData POST)    [WP4]

SIMATIC ──→ Snowflake  (MQTT → Snowpipe, micro-batch JSON)
Mendix  ──→ Snowflake  (REST webhook, event-driven JSON)
SAP     ──→ Snowflake  (OData extract, scheduled batch)

Snowflake (Bronze → Silver → Gold)            [WP5]
    ↓ native query (no connector)
Streamlit in Snowflake (SiS)                  [WP6]

Unified cockpit (HMI 1 + 2 + 3 + SAP panel)  [WP7]
Runtime agent layer (anomaly + cycle-end)     [WP8 — stretch]
```

**Key architectural principle:** The production order number is the spine of the entire stack. Created in SAP → passed to Mendix → stamped onto sensor readings by SIMATIC → used as the join key in Snowflake Gold.

**Dashboard deployment:** WP6 runs as a Streamlit in Snowflake (SiS) application — co-located with the data, no external connector required.

**Reference diagrams:**
- `industrial_iot_architecture_model_a.svg` — real architecture (production reference)
- `industrial_iot_architecture_demo_stack.svg` — demo stack with WP labels

---

## The four panels (WP7 unified cockpit)

| Panel | Tab | Persona | Data source | Purpose |
|---|---|---|---|---|
| SAP panel | "SAP" | SAP planner | WP4 OData | Release production orders |
| Mendix panel | "Operator" | Production operator | WP3 REST + WP4 OData | Start cycle, confirm completion, handle deviations |
| Machine panel | "Machine" | Machine operator | WP2 REST (5s poll) | Live gauges: temperature, vacuum, moisture |
| Analytics panel | "Analytics" | Process engineer | Snowflake Gold (SiS) | Historical cycle analysis, efficiency trends |

No user authentication — panel boundary implies persona. (ADR-007)

---

## Demo workflows

Six workflows are executable from the WP7 unified cockpit:

| # | Workflow | Panel | Trigger |
|---|---|---|---|
| WF1 | Release production order | SAP panel | Manual |
| WF2 | Start drying cycle | Mendix panel | Manual |
| WF3 | Monitor live cycle | Machine panel | Automatic |
| WF4 | Cycle completion + confirmation | Mendix panel | Automatic signal + manual confirm |
| WF5 | Cycle timeout — deviation handling | Mendix panel | Automatic |
| WF6 | SAP confirmation failure | Mendix panel | Automatic on SAP error |

Full workflow definitions, preconditions, step-by-step data flows, and the order state machine: see `DOMAIN-MODEL.md`.

---

## Workpackage map

| WP | Name | Produces | Depends on | Status |
|---|---|---|---|---|
| WP1 | Sensor simulator | MQTT stream | — | NOT STARTED |
| WP2 | SIMATIC mock | REST process state API | WP1 | NOT STARTED |
| WP3 | Mendix mock | OData-style REST API + operator UI | WP2, WP4 | NOT STARTED |
| WP4 | SAP mock | OData endpoints (orders, materials, GR) | — | NOT STARTED |
| WP5 | Snowflake data layer | Bronze/Silver/Gold tables | WP1, WP3, WP4 | NOT STARTED |
| WP6 | Analytical dashboard (SiS) | Streamlit in Snowflake app | WP5 | NOT STARTED |
| WP7 | Unified cockpit | Integrated 4-panel demo interface | WP2–WP6 | NOT STARTED |
| WP8 | Runtime agent layer | Anomaly detection, cycle-end signal | WP2, WP5 | STRETCH |

**Execution order:**
- WP1 and WP4 can start immediately (no upstream dependencies)
- WP2 after WP1 MQTT schema is stable
- WP3 after WP2 REST spec and WP4 OData spec are stable
- WP5 after WP1 schema stable; WP6 after WP5 Gold schema stable
- WP7 is the integration milestone — requires WP2–WP6 complete
- WP8 is a stretch goal

---

## Repository structure

```
/                           Repo root
  README.md                 This file
  CONTRIBUTING.md           Code standards — read before writing any code
  SDLC.md                   Delivery process — phases, DoD, gates
  AI-DEV.md                 AI-assisted development methodology
  DOMAIN-MODEL.md           Canonical schemas, workflows, data flows ← start here
  architecture_handover.md  Full project context and interview prep
  industrial_iot_architecture_model_a.svg      Real architecture diagram
  industrial_iot_architecture_demo_stack.svg   Demo stack diagram (WP labels)

/contracts
  interface-contracts.md    All inter-WP interface schemas (master reference)
  mqtt-schema.json          MQTT topic + payload schema
  rest-endpoints.yaml       REST API specs (WP2, WP3, WP4 mocks)
  snowflake-schema.sql      Bronze/Silver/Gold DDL (Snowflake)
  seed-data/                Reference data for development and testing
    material_masters.json   4 transformer types with full spec
    production_orders.json  3 orders (RELEASED / CONFIRMED / ABORTED)
    historical_cycles.json  20 completed cycles for Gold layer seed
    README.md               How to use seed data in tests
  validators/               Schema validation scripts
    validate_c1_mqtt.py     MQTT reading validator
    validate_c10_cycle_event.py  CycleEvent validator
    validate_c12_gold_cycle.py   Gold cycle row validator

/docs
  architecture.md           Layer-by-layer architecture reference
  decisions.md              Architecture Decision Records (ADR-001 to ADR-008)
  delivery-plan.md          Phase map, milestones, gates, demo checklist

/wp1-sensor-sim             Sensor + OPC-UA simulator
/wp2-simatic-mock           SIMATIC historian + REST publisher
/wp3-mendix-mock            Mendix operator UI + SAP connector mock
/wp4-sap-mock               SAP S/4HANA OData mock service
/wp5-snowflake-layer        Snowflake ingestion pipeline + transformations
/wp6-analytical-dashboard   Streamlit in Snowflake analytical dashboard
/wp7-unified-cockpit        Integrated 4-panel HMI cockpit
/wp8-agent-layer            Runtime AI agents (stretch)
```

---

## Where best practices live

| Topic | Document |
|---|---|
| Object schemas, workflows, data flows, state machine | `DOMAIN-MODEL.md` ← start here |
| Code standards (typing, naming, testing, logging, config) | `CONTRIBUTING.md` |
| Delivery phases, DoD, seam validation, milestones | `SDLC.md` |
| Agent session protocol, prompt patterns, skill library | `AI-DEV.md` |
| Interface contracts (field-level schemas) | `contracts/interface-contracts.md` |
| Reference data for development and testing | `contracts/seed-data/` |
| Architecture decisions and trade-offs | `docs/decisions.md` |
| Phase map, milestone gates, demo readiness checklist | `docs/delivery-plan.md` |
| Per-WP scope, DoD, session handover | `wp{n}/WP-BRIEF.md` |

---

## Running the demo

**Infrastructure prerequisites:**
- Mosquitto MQTT broker (project-level — see `docker-compose.yml`)
- Snowflake account with credentials in `.env`

**Start order:**
```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Start independent services (any order)
cd wp4-sap-mock && python src/main.py &
cd wp1-sensor-sim && python src/main.py &   # starts paused, activates on WF2

# 3. Start dependent services
cd wp2-simatic-mock && python src/main.py &
cd wp3-mendix-mock && python src/main.py &
cd wp5-snowflake-layer && python src/main.py &

# 4. Open unified cockpit
cd wp7-unified-cockpit && streamlit run src/app.py
```

**Demo timing:** Full WF1 → WF4 run takes ~12–15 minutes wall clock at 60× cycle compression.

> Detailed per-WP setup instructions added as WPs are completed.

---

## AI-assisted development

Built using Claude Code with a structured agent-per-workpackage approach. Each WP brief (`WP-BRIEF.md`) serves as the agent prompt document. Interface contracts are agreed before implementation begins. Seam validation between WPs is built into the delivery process.

See `AI-DEV.md` for the full methodology and `SDLC.md` for the delivery process.
