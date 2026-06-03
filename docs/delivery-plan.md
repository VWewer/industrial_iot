# Delivery Plan

> **Status:** v1.0 — June 2026  
> **Purpose:** Visual milestone map, phase gate definitions, and execution sequence. Read alongside `SDLC.md` which defines what happens inside each phase.

---

## Milestone map

```
M0 ──────────────────────────────────────────────────────────────────
│  CONTRACTS + DOMAIN MODEL COMPLETE                        ✓ DONE
│  DOMAIN-MODEL.md, interface-contracts.md, schemas,
│  seed data, ADRs all stable
└─────────────────────────────────────────────────────────────────────

         ┌─────────────┐         ┌─────────────┐
         │     WP1     │         │     WP4     │
         │Sensor Sim   │         │  SAP mock   │
         │  (MQTT)     │         │  (OData)    │
         └──────┬──────┘         └──────┬──────┘
                │                       │
M1 ─────────────┴───────────────────────┴────────────────────────────
│  FOUNDATION RUNNING                              TARGET: Week 1-2
│  WP1 Phase 4 complete — MQTT stream validated
│  WP4 Phase 4 complete — SAP OData endpoints validated
└─────────────────────────────────────────────────────────────────────

         ┌─────────────┐         ┌─────────────┐
         │     WP2     │         │     WP3     │
         │SIMATIC mock │         │Mendix mock  │
         │  (REST)     │◄────────│  (UI+SAP)   │
         └──────┬──────┘         └──────┬──────┘
                │                       │
M2 ─────────────┴───────────────────────┴────────────────────────────
│  MID-STACK RUNNING                               TARGET: Week 2-3
│  WP2 Phase 4 complete — process state API validated
│  WP3 Phase 4 complete — operator workflow API validated
│  All 6 workflows exercisable via API calls (no UI yet)
└─────────────────────────────────────────────────────────────────────

         ┌──────────────────────────────────────┐
         │               WP5                    │
         │   Snowflake Bronze → Silver → Gold   │
         │   (Snowpipe + transforms)            │
         └──────────────────────┬───────────────┘
                                │
M3 ─────────────────────────────┴────────────────────────────────────
│  DATA LAYER COMPLETE                             TARGET: Week 3-4
│  WP5 Phase 4 complete
│  Gold layer queryable with seed data (20+ historical cycles)
│  Live cycle end-to-end: WP1→MQTT→WP5→Gold row in < 60s
└─────────────────────────────────────────────────────────────────────

         ┌──────────────────────────────────────┐
         │               WP6                    │
         │  Streamlit in Snowflake (SiS)        │
         │  Analytical dashboard                │
         └──────────────────────┬───────────────┘
                                │
M4 ─────────────────────────────┴────────────────────────────────────
│  DASHBOARD LIVE                                  TARGET: Week 4-5
│  WP6 Phase 4 complete
│  SiS app deployed, all 3 analytics stories visible
│  Cycle overview, cycle detail, efficiency analysis all working
└─────────────────────────────────────────────────────────────────────

         ┌──────────────────────────────────────┐
         │               WP7                    │
         │    Unified Cockpit                   │
         │  HMI 1 + HMI 2 + HMI 3 + SAP panel  │
         └──────────────────────┬───────────────┘
                                │
M5 ─────────────────────────────┴────────────────────────────────────
│  INTEGRATION COMPLETE — PORTFOLIO READY          TARGET: Week 5-6
│  WP7 Phase 4 complete
│  Full demo workflow (WF1→WF4) runs end-to-end from WP7 UI
│  All 6 workflows demonstrable
│  Demo timing: ~12-15 minutes wall clock for full WF1→WF4 run
└─────────────────────────────────────────────────────────────────────

         ┌──────────────────────────────────────┐
         │               WP8                    │
         │  Runtime Agent Layer (STRETCH)       │
         │  Anomaly detection, cycle-end pred.  │
         └──────────────────────┬───────────────┘
                                │
M6 ─────────────────────────────┴────────────────────────────────────
│  AGENT LAYER (STRETCH)
└─────────────────────────────────────────────────────────────────────
```

---

## Phase gates — entry and exit criteria

### Gate M0 → M1 (start WP1 and WP4)

**Entry:** Phase 0 complete (all contracts stable, DOMAIN-MODEL.md written)

**Exit (M1):**
- WP1: `pytest tests/` passes, MQTT stream publishing all 3 sensor types, sample payload validated against `contracts/mqtt-schema.json`
- WP4: `pytest tests/` passes, all OData endpoints return correct seed data, sample responses validated against `contracts/rest-endpoints.yaml`

---

### Gate M1 → M2 (start WP2 and WP3)

**Entry:** M1 complete. WP1 MQTT schema signed off. WP4 OData spec signed off.

**Exit (M2):**
- WP2: process state REST API validated (`GET /process-state/oven-01` returns correct HistorianSnapshot schema)
- WP3: operator workflow API validated — all 6 workflow steps exercisable via API calls
- Integration test: WP1 → MQTT → WP2 subscriber → HistorianSnapshot updates within 10s

---

### Gate M2 → M3 (start WP5)

**Entry:** M2 complete. WP1 MQTT stream stable. WP3 REST API stable. WP4 OData stable.

**Exit (M3):**
- WP5: all Bronze tables populating from correct sources
- Silver transforms running, deduplication correct
- Gold `gold_cycle_summary` produces correct row for a completed test cycle
- Seed data loaded: 20 historical cycles visible in Gold on first run
- Query API (or direct Snowflake query) returns Gold data correctly

---

### Gate M3 → M4 (start WP6)

**Entry:** M3 complete. Gold layer stable and queryable. Snowflake account confirmed.

**Exit (M4):**
- WP6 SiS app deployed
- Cycle overview page renders with correct seed data
- Cycle detail view shows correct KPIs and time-series for at least 3 historical cycles
- Efficiency analysis page renders correctly
- Filters functional

---

### Gate M4 → M5 (start WP7)

**Entry:** M4 complete. WP2, WP3, WP4 all running locally. WP5 Gold queryable. WP6 SiS deployed.

**Exit (M5 — portfolio ready):**
- Full demo workflow WF1 → WF4 runs end-to-end from WP7 UI without touching any other interface
- WF5 (cycle timeout) demonstrable
- WF6 (SAP confirmation failure) demonstrable
- HMI 1 live readings update within 10s of WP1 publishing
- HMI 3 shows new cycle in analytics within 60s of cycle completion
- Demo can run from cold start in < 5 minutes

---

## Workpackage execution timeline (indicative)

| Week | Focus | Milestone |
|---|---|---|
| 1 | WP4 (SAP mock) + WP1 (sensor sim) in parallel | M1 |
| 2 | WP2 (SIMATIC mock) | M2 partial |
| 3 | WP3 (Mendix mock) + WP5 kickoff | M2, M3 partial |
| 4 | WP5 completion | M3 |
| 5 | WP6 (SiS dashboard) | M4 |
| 6 | WP7 (unified cockpit) | M5 |
| 7+ | WP8 (agent layer, stretch) | M6 |

---

## Demo readiness checklist (pre-presentation)

Run this before any demo:

```
Infrastructure
[ ] docker-compose up -d — Mosquitto broker running
[ ] Snowflake account accessible

Services
[ ] WP4 SAP mock running (port 8004)
[ ] WP1 sensor sim running (paused, waiting for WF2 trigger)
[ ] WP2 SIMATIC mock running (port 8002)
[ ] WP3 Mendix mock running (port 8003)
[ ] WP5 Snowflake layer running (port 8005)

Data
[ ] Seed data loaded — 20 historical cycles visible in WP6 analytics
[ ] ORD-2026-00042 in RELEASED state (ready for WF1 → WF2)

Cockpit
[ ] WP7 unified cockpit running (http://localhost:8501)
[ ] All 4 panels accessible and loading without errors
[ ] HMI 1 shows oven-01 in IDLE state
[ ] HMI 2 shows released order ORD-2026-00042
[ ] HMI 3 shows 20+ historical cycles in overview table
```
