# WP7 — Unified Cockpit (Integration Milestone)

## Status: NOT STARTED — blocked on WP2–WP6

> **v1.1 — June 2026:** 4-panel layout defined (SAP + Mendix + Machine + Analytics). 6 workflows mapped to panels. SiS integration approach clarified. No user authentication (ADR-007).

---

## Role in the architecture

WP7 is the integration milestone and the primary demo interface. It is a single Streamlit multi-page application that presents all four panels in one interface:

| Panel | Tab label | HMI | Data source | Workflows |
|---|---|---|---|---|
| SAP panel | "SAP" | — | WP4 REST | WF1 — release order |
| Mendix panel | "Operator" | HMI 2 | WP3 REST + WP4 REST | WF2, WF4, WF5, WF6 |
| Machine panel | "Machine" | HMI 1 | WP2 REST (live poll) | WF3 — monitor live cycle |
| Analytics panel | "Analytics" | HMI 3 | WP5 query API or Snowflake | WF4 outcome visible |

**No user authentication.** Panel boundary implies persona. Tab label implies role. (ADR-007)

**WP7 does not implement business logic.** It wires existing services. Bugs found in WP7 are fixed in the upstream WP — not worked around in WP7.

---

## Demo workflow (full end-to-end)

The complete demo runs as follows from WP7 UI:

```
[SAP Panel]
  1. User sees ORD-2026-00042 in RELEASED state
  2. User clicks "Release Order" → WP4 PATCH → order visible in Mendix panel
     (order already RELEASED in seed data — this confirms / demonstrates the action)

[Operator Panel]
  3. Operator sees released order, material spec, planned duration
  4. Operator clicks "Start Cycle" → WP3 → cycle_started event → WP2 stamping begins
  5. Machine panel goes live

[Machine Panel]
  6. Live temperature / vacuum / moisture gauges updating every 5s
  7. Elapsed cycle time counting up
  8. After ~8-12 real minutes: "THRESHOLD MET" indicator fires

[Operator Panel]
  9. Alert appears: "Cycle complete — moisture below threshold. Confirm to post to SAP."
  10. Operator reviews final readings, clicks "Confirm and Post to SAP"
  11. WP3 → SAP confirmation POST → WP4 returns confirmation number
  12. Success message: "Confirmed. SAP ref: [number]"

[Analytics Panel]
  13. Auto-refresh: new cycle row appears in cycle overview table within 60s
  14. Click row → cycle detail: KPI cards, time-series chart showing the drying curve
```

---

## What this WP consumes

| Contract | Source | What WP7 uses it for |
|---|---|---|
| C2 — Process state | WP2 `GET /process-state/oven-01` | Machine panel live gauges |
| C3 — Order context write | WP2 `PUT /active-order` | Not directly — WP3 calls this |
| C4 — Order state | WP3 `GET /orders` | Mendix panel order list |
| C5 — Confirmation trigger | WP3 `POST /orders/{id}/confirm` | Mendix panel confirm button |
| C6 — Production orders | WP4 `GET /odata/v1/ProductionOrders` | SAP panel order list |
| C7 — Material master | WP4 `GET /odata/v1/MaterialMasters` | Material spec display |
| C12 — Gold query | WP5 `GET /gold/cycles` + `/gold/cycles/{id}` | Analytics panel |

---

## Scope

### Must implement

**1. App structure**
- Streamlit multi-page app with 4 tabs in sidebar: SAP / Operator / Machine / Analytics
- Shared state: `st.session_state` holds active `order_id`, current `oven_status`, selected cycle for detail view
- Unified visual theme: consistent colour palette, font, component sizes across all tabs

**2. SAP panel**
- Order list: all ProductionOrders from WP4, columns: order_id, material, plant, status, planned_start
- Filter: status (RELEASED / RUNNING / CONFIRMED / all)
- "Release Order" button (only enabled for CREATED status orders)
- On release: `PATCH /odata/v1/ProductionOrders/{id}` → status = RELEASED
- Status badge colours: RELEASED = blue, RUNNING = amber, CONFIRMED = green, ABORTED = grey

**3. Operator (Mendix) panel**
- RELEASED orders list (from WP3, polling WP4 in background)
- Selected order detail: material spec card (insulation class, target moisture, standard duration)
- "Start Cycle" button (enabled when order selected + oven idle)
  - On click: `POST /orders/{id}/start` → WP3 → triggers WF2 chain
- Cycle-active view (when status = RUNNING):
  - Current elapsed time vs standard duration
  - Live moisture reading (polled from WP2, updates every 5s)
  - Status: RUNNING / THRESHOLD MET / TIMEOUT
- Confirm section (appears when status = THRESHOLD_MET):
  - Final readings summary (moisture, peak temp, elapsed)
  - "Confirm and Post to SAP" button → `POST /orders/{id}/confirm` → WP3
  - Success state: SAP confirmation number displayed
  - Error state (WF6): error message + "Retry" button
- Timeout section (appears when status = TIMEOUT):
  - Warning: elapsed vs max_cycle_minutes
  - "Extend Cycle" input (additional minutes) + button
  - "Abort Cycle" button + confirmation modal

**4. Machine panel**
- Live gauges (auto-refresh every 5s via `st.rerun()` or `streamlit-autorefresh`):
  - Temperature gauge: 0–160°C, setpoint line at target_temperature_degC
  - Vacuum gauge: 0–50 mbar, setpoint line at target_vacuum_mbar
  - Moisture gauge: 0–6000 ppm, threshold line at target_moisture_ppm
- Cycle status indicator: IDLE / RUNNING / THRESHOLD MET / TIMEOUT
- Active order badge (order_id + material_description) — null when idle
- Elapsed time counter (cycle time, not wall clock)
- Last reading timestamp

**5. Analytics panel**
- Embed or replicate WP6 analytics
- Preferred approach: replicate queries and charts directly (WP7 owns the code, same SQL)
- Alternative: iframe link to SiS (simpler, but breaks unified theme)
- Cycle overview table: same as WP6 (recent 20 cycles)
- On cycle confirm in Operator panel: trigger analytics panel refresh via session state flag
- Minimum: cycle overview and cycle detail for most recently completed cycle

**6. Visual theme**
All panels use this colour palette:
```python
COLOURS = {
    "primary":    "#1B4F72",   # Dark blue — headers, primary buttons
    "running":    "#F39C12",   # Amber — RUNNING status, in-progress
    "success":    "#1E8449",   # Green — CONFIRMED, spec met
    "warning":    "#E74C3C",   # Red — TIMEOUT, spec not met, errors
    "neutral":    "#7F8C8D",   # Grey — IDLE, ABORTED
    "background": "#F8F9FA",   # Light grey — card backgrounds
    "text":       "#2C3E50",   # Dark — primary text
}
```

### Out of scope
- New business logic (all logic lives in WP2–WP5)
- User authentication / role switching (ADR-007)
- Multi-oven support (ADR-003)
- Export or reporting features

---

## Tech stack

| Library | Version | Purpose |
|---|---|---|
| `streamlit` | `1.35.0` | App framework |
| `plotly` | `5.22.0` | Gauges, time-series, charts |
| `httpx` | `0.27.0` | Async calls to WP2/WP3/WP4/WP5 REST APIs |
| `pandas` | `2.2.2` | DataFrame manipulation |
| `python-dotenv` | `1.0.1` | Config loading |

---

## Configuration

```ini
WP2_API_URL=http://localhost:8002
WP3_API_URL=http://localhost:8003
WP4_API_URL=http://localhost:8004
WP5_API_URL=http://localhost:8005
MACHINE_PANEL_REFRESH_S=5
ANALYTICS_REFRESH_S=30
OVEN_ID=oven-01
COCKPIT_PORT=8501
```

---

## Folder structure

```
wp7-unified-cockpit/
  WP-BRIEF.md
  README.md
  requirements.txt
  .env.example
  src/
    app.py                  Entry point: streamlit run src/app.py
    panels/
      sap_panel.py          SAP tab: order list, release action
      operator_panel.py     Mendix tab: start, confirm, timeout handling
      machine_panel.py      Machine tab: live gauges, status
      analytics_panel.py    Analytics tab: cycle overview + detail
    api_clients/
      wp2_client.py         WP2 REST client (process state)
      wp3_client.py         WP3 REST client (order ops, confirm)
      wp4_client.py         WP4 REST client (orders, materials)
      wp5_client.py         WP5 REST client (Gold queries)
    charts.py               Plotly gauge and chart builders
    theme.py                Colour palette, CSS, component helpers
    state.py                Session state schema and helpers
    models.py               Pydantic models for API responses
  tests/
    test_panels.py          Panel render tests (mock API clients)
    test_api_clients.py     API client tests (mock HTTP responses)
    integration/
      test_full_workflow.py WF1→WF4 end-to-end with live upstream WPs
```

---

## Definition of Done

- [ ] Standard DoD (see SDLC.md Phase 3)
- [ ] All 4 panels render without errors against live upstream services
- [ ] Full demo workflow WF1 → WF4 executable end-to-end from WP7 UI
- [ ] WF5 (cycle timeout) demonstrable: timeout warning appears, extend and abort both work
- [ ] WF6 (SAP confirmation failure): error state renders, retry works
- [ ] Machine panel live readings update within 10s of WP1 publishing
- [ ] Operator panel threshold-met signal appears within 10s of WP2 detecting it
- [ ] Analytics panel shows new cycle within 60s of cycle confirmation
- [ ] Unified visual theme consistent across all 4 panels
- [ ] No hardcoded data — all content from live upstream services
- [ ] Demo readiness checklist in `docs/delivery-plan.md` passes

## Open items

- [ ] Confirm analytics panel approach: replicate WP6 queries vs iframe to SiS
- [ ] Confirm live gauge library: Plotly `go.Indicator` (native) vs `streamlit-gauge-chart` (SiS-incompatible — avoid)
- [ ] Confirm auto-refresh strategy: `streamlit-autorefresh` (machine panel 5s) vs `st.fragment` (Streamlit 1.33+)
- [ ] Agree unified colour palette with WP6 before WP7 kickoff

## Session handover notes

> *To be filled by the agent at the end of each session.*
