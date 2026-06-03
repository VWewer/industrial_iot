# Delivery Plan

> **Status:** v1.1 -- June 2026
> **Changes from v1.0:** Added current-status section, updated milestone status from actuals, fixed port numbers in demo checklist.

---

## Where we are right now

> Last updated: 2026-06-03

```
M0  CONTRACTS + DOMAIN MODEL       [DONE]
M1  FOUNDATION RUNNING             [IN PROGRESS -- WP1 done, WP4 P4 blocked on WP3]
M2  MID-STACK RUNNING              [NOT STARTED]
M3  DATA LAYER COMPLETE            [NOT STARTED]
M4  DASHBOARD LIVE                 [NOT STARTED]
M5  INTEGRATION + PORTFOLIO READY  [NOT STARTED]
M6  AGENT LAYER (stretch)          [NOT STARTED]
```

**Current WP status:**

| WP | Name | Phase | Status | Blocker |
|---|---|---|---|---|
| WP1 | Sensor sim | P4 | COMPLETE | -- |
| WP4 | SAP mock | P3 | COMPLETE -- P4 pending | Needs WP3 to consume C5 |
| WP2 | SIMATIC mock | -- | NOT STARTED | Unblocked (WP1 done) |
| WP3 | Mendix mock | -- | NOT STARTED | Unblocked (WP4 done) |
| WP5 | Snowflake layer | -- | NOT STARTED | Needs M2 (WP1+WP3+WP4 P4) |
| WP6 | SiS dashboard | -- | NOT STARTED | Needs M3 |
| WP7 | Unified cockpit | -- | NOT STARTED | Needs M4 |
| WP8 | Agent layer | -- | STRETCH | Needs M5 |

**What unblocks M1 (the current bottleneck):**
WP4 Phase 4 requires WP3 (Mendix mock) to exist so it can receive a `POST /odata/v1/OperationConfirmations` call (Contract C5) and validate the full confirmation flow. Start WP3 to unblock M1.

**Recommended next:** start WP2 and WP3 in parallel. Both are unblocked.

---

## Where project control docs live

| What you want | Where to find it |
|---|---|
| Live WP phase status (the tracker) | `architecture_handover.md` Section 0a |
| Milestone map + gate criteria | This file (`docs/delivery-plan.md`) |
| What each phase means + DoD | `SDLC.md` |
| Per-WP scope, contracts, DoD | `wp{n}/WP{n}-BRIEF.md` |
| Architecture decisions (ADRs) | `docs/decisions.md` |
| Canonical object schemas | `DOMAIN-MODEL.md` |
| Inter-WP interface contracts | `contracts/interface-contracts.md` |
| Known issues + learnings | `AI-DEV.md` Section 14 |

**There is no separate WBS file.** The WP briefs collectively are the WBS: each WP is a work package with explicit scope (must implement / out of scope), a DoD checklist, and dependencies stated. The milestone map below shows the sequencing.

---

## Milestone map

```
M0 ----------------------------------------------------------------
|  CONTRACTS + DOMAIN MODEL COMPLETE                   [DONE]
|  DOMAIN-MODEL.md, interface-contracts.md, schemas,
|  seed data, ADRs all stable
-------------------------------------------------------------------

         +-------------+         +-------------+
         |     WP1     |         |     WP4     |
         | Sensor sim  |         |  SAP mock   |
         |   (MQTT)    |         |  (OData)    |
         +------+------+         +------+------+
                |                       |
M1 -------------+---[ IN PROGRESS ]-----+---------------------------
|  FOUNDATION RUNNING                        TARGET: Week 1-2
|  WP1 Phase 4 DONE
|  WP4 Phase 4 pending -- needs WP3 to consume C5
-------------------------------------------------------------------

         +-------------+         +-------------+
         |     WP2     |         |     WP3     |
         | SIMATIC mock|         | Mendix mock |
         |   (REST)    |<--------|  (UI+SAP)   |
         +------+------+         +------+------+
                |                       |
M2 -------------+---[ NOT STARTED ]-----+---------------------------
|  MID-STACK RUNNING                         TARGET: Week 2-3
|  WP2 Phase 4 -- process state API validated
|  WP3 Phase 4 -- operator workflow API validated
|  Integration: WP1 -> MQTT -> WP2 subscriber updates within 10s
-------------------------------------------------------------------

         +--------------------------------------+
         |               WP5                    |
         |   Snowflake Bronze -> Silver -> Gold |
         |   + Snowflake ERD (Mermaid)          |
         +---------------------+----------------+
                               |
M3 ----------------------------+---[ NOT STARTED ]------------------
|  DATA LAYER COMPLETE                       TARGET: Week 3-4
|  WP5 Phase 4 -- Gold layer queryable
|  Live cycle end-to-end: WP1->MQTT->WP5->Gold < 60s
|  Snowflake ERD published in docs/snowflake-erd.md
-------------------------------------------------------------------

         +--------------------------------------+
         |               WP6                    |
         |  Streamlit in Snowflake (SiS)        |
         |  Analytical dashboard                |
         +---------------------+----------------+
                               |
M4 ----------------------------+---[ NOT STARTED ]------------------
|  DASHBOARD LIVE                            TARGET: Week 4-5
|  WP6 Phase 4 -- SiS app deployed
|  All 3 analytics stories visible
-------------------------------------------------------------------

         +--------------------------------------+
         |               WP7                    |
         |    Unified Cockpit                   |
         |  HMI 1 + HMI 2 + HMI 3 + SAP panel  |
         +---------------------+----------------+
                               |
M5 ----------------------------+---[ NOT STARTED ]------------------
|  INTEGRATION COMPLETE -- PORTFOLIO READY   TARGET: Week 5-6
|  WP7 Phase 4 -- full demo workflow WF1->WF4 end-to-end
|  All 6 workflows demonstrable
|  Demo timing: ~12-15 min wall clock
-------------------------------------------------------------------

         +--------------------------------------+
         |               WP8                    |
         |  Runtime Agent Layer (STRETCH)       |
         +---------------------+----------------+
                               |
M6 ----------------------------+---[ STRETCH ]----------------------
|  AGENT LAYER
-------------------------------------------------------------------
```

---

## Phase gates -- entry and exit criteria

### Gate M0 -> M1 (start WP1 and WP4)

**Entry:** Phase 0 complete (all contracts stable, DOMAIN-MODEL.md written)

**Exit (M1):**
- WP1: `pytest tests/` passes, MQTT stream publishing all 3 sensor types, sample payload validated against `contracts/mqtt-schema.json`
- WP4: `pytest tests/` passes, all OData endpoints return correct seed data, sample responses validated against `contracts/rest-endpoints.yaml`

---

### Gate M1 -> M2 (start WP2 and WP3)

**Entry:** M1 complete. WP1 MQTT schema signed off. WP4 OData spec signed off.

**Exit (M2):**
- WP2: process state REST API validated (`GET /process-state/oven-01` returns correct HistorianSnapshot schema)
- WP3: operator workflow API validated -- all 6 workflow steps exercisable via API calls
- Integration test: WP1 -> MQTT -> WP2 subscriber -> HistorianSnapshot updates within 10s

---

### Gate M2 -> M3 (start WP5)

**Entry:** M2 complete. WP1 MQTT stream stable. WP3 REST API stable. WP4 OData stable.

**Exit (M3):**
- WP5: all Bronze tables populating from correct sources
- Silver transforms running, deduplication correct
- Gold `gold_cycle_summary` produces correct row for a completed test cycle
- Seed data loaded: 20 historical cycles visible in Gold on first run
- Query API returns Gold data correctly
- Snowflake schema ERD published (`docs/snowflake-erd.md`)

---

### Gate M3 -> M4 (start WP6)

**Entry:** M3 complete. Gold layer stable and queryable. Snowflake account confirmed.

**Exit (M4):**
- WP6 SiS app deployed
- Cycle overview page renders with correct seed data
- Cycle detail view shows correct KPIs and time-series for at least 3 historical cycles
- Efficiency analysis page renders correctly
- Filters functional

---

### Gate M4 -> M5 (start WP7)

**Entry:** M4 complete. WP2, WP3, WP4 all running locally. WP5 Gold queryable. WP6 SiS deployed.

**Exit (M5 -- portfolio ready):**
- Full demo workflow WF1 -> WF4 runs end-to-end from WP7 UI without touching any other interface
- WF5 (cycle timeout) demonstrable
- WF6 (SAP confirmation failure) demonstrable
- HMI 1 live readings update within 10s of WP1 publishing
- HMI 3 shows new cycle in analytics within 60s of cycle completion
- Demo can run from cold start in < 5 minutes

---

## Workpackage execution timeline (indicative)

| Week | Focus | Milestone |
|---|---|---|
| 1 | WP4 (SAP mock) + WP1 (sensor sim) | M1 partial (WP1 done, WP4 P4 pending) |
| 2 | WP2 + WP3 in parallel | M1 complete, M2 partial |
| 3 | WP3 finish + WP5 kickoff | M2 complete, M3 partial |
| 4 | WP5 completion | M3 complete |
| 5 | WP6 (SiS dashboard) | M4 complete |
| 6 | WP7 (unified cockpit) | M5 complete |
| 7+ | WP8 (agent layer, stretch) | M6 |

---

## Demo readiness checklist (pre-presentation)

Run this before any demo:

```
Infrastructure
[ ] Mosquitto broker running (Windows Service on port 1883, or docker compose up mosquitto)
[ ] Snowflake account accessible

Services (ports -- adjust CONTROL_API_PORT if 8000 excluded by Windows)
[ ] WP4 SAP mock running (port 8003)
[ ] WP1 sensor sim running (port 8080 on Windows, 8000 in Docker)
[ ] WP2 SIMATIC mock running (port 8001)
[ ] WP3 Mendix mock running (port 8002)
[ ] WP5 Snowflake layer running (port 8005)

Data
[ ] Seed data loaded -- 20 historical cycles visible in WP6 analytics
[ ] ORD-2026-00001 in RELEASED state (ready for WF1 -> WF2)

Cockpit
[ ] WP7 unified cockpit running (http://localhost:8501)
[ ] All 4 panels accessible and loading without errors
[ ] HMI 1 shows oven-01 in IDLE state
[ ] HMI 2 shows released order ORD-2026-00001
[ ] HMI 3 shows 20+ historical cycles in overview table
```
