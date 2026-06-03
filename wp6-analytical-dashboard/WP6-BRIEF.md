# WP6 — Analytical Dashboard (Streamlit in Snowflake)

## Status: NOT STARTED

> **v1.1 — June 2026:** Updated to deploy as Streamlit in Snowflake (SiS) — see ADR-006. DuckDB direct connection removed. All three analytics stories in scope.

---

## Role in the architecture

WP6 is HMI 3 — the process engineer's analytical interface. It runs as a Streamlit in Snowflake (SiS) application, co-located with the Gold layer in WP5. It presents historical cycle analysis, efficiency trends, and cycle comparison. It does not interact with live sensor data directly — that is WP7's machine panel.

**Deployment:** Streamlit in Snowflake. The app queries the Gold layer via native Snowflake SQL — no external connector, no credentials managed in the app code. This is the architecturally coherent endpoint of the "Snowflake as single analytical hub" claim.

---

## What this WP produces

A deployed Streamlit in Snowflake application answering:
- Did this drying cycle meet the moisture spec?
- Was it shorter or longer than the standard cycle time? Why?
- Which transformer types consistently run long?
- What does the sensor profile look like for a given cycle?
- What is the efficiency trend across material types?

---

## What this WP consumes

**Contract C12** — Gold layer tables in Snowflake (native SQL query, no connector)

| Object | Query pattern |
|---|---|
| `gold_cycle_summary` | Full table access, filtered by date/material/plant |
| `v_cycle_efficiency` | Aggregated view — no additional computation needed |
| `v_recent_cycles` | Last 20 completed cycles for overview table |
| `silver_sensor_readings` | Per-cycle sensor time-series for detail view |

**Full schemas:** `DOMAIN-MODEL.md` Section 6.

---

## Scope

### Must implement

**1. Cycle overview page (default / landing)**
- Table of recent cycles (`v_recent_cycles`) with columns:
  - `order_id`, `material_description`, `plant`, `actual_duration_minutes`, `standard_cycle_minutes`, `delta_minutes`, `spec_met` (✓/✗), `cycle_end_time`
- Colour-code rows: green = spec met, amber = ≤10% over standard, red = >10% over or spec not met
- Click a row → navigate to cycle detail view (pass `order_id` via session state)

**2. Cycle detail view**
- Header: `order_id`, `material_description`, `plant`, `oven_id`, `operator_id`, `sap_confirmation_number`
- KPI cards (4):
  - Actual duration vs standard (with delta)
  - Peak temperature (°C)
  - Final moisture (ppm) vs target
  - Spec met: ✓ / ✗
- Time-series chart: temperature, vacuum, moisture over cycle elapsed time
  - X-axis: cycle elapsed time (minutes, compressed)
  - Y-axis: dual — left = °C / mbar, right = ppm
  - Show threshold line for moisture target
  - Characteristic drying curve visible: moisture decaying, temp holding

**3. Efficiency analysis page**
- Bar chart: average actual duration vs standard cycle time by material type
- Scatter plot: final moisture ppm vs actual duration (colour = material type, shape = spec met)
- Summary stats table from `v_cycle_efficiency`:
  - `material_description`, `cycle_count`, `avg_delta_minutes`, `pct_spec_met`, `avg_final_moisture_ppm`

**4. Sidebar filters (apply across all pages)**
- Date range picker (default: last 90 days)
- Material type (multi-select, populated from Gold data)
- Plant (multi-select: regensburg, kirchheim)
- Outcome (All / Spec met only / Over standard only / Spec failed)

**5. Auto-refresh**
- Poll Snowflake every 30 seconds (configurable via SiS session variable)
- New completed cycles appear in overview without page reload
- Use `st.rerun()` with `time.sleep()` in a background thread or `st.fragment` (SiS supported)

### Out of scope
- Live sensor feed (that's WP7 machine panel)
- Predictive analytics / ML (WP8 stretch)
- Export to PDF/Excel
- User authentication

---

## Tech stack

SiS environment — no pip install at runtime. Libraries must be available in the SiS package registry.

| Library | Purpose | SiS available? |
|---|---|---|
| `streamlit` | App framework | Yes (native) |
| `snowflake.snowpark` | Native Snowflake query in SiS | Yes (native) |
| `plotly` | Charts (time-series, bar, scatter) | Yes |
| `pandas` | DataFrame manipulation | Yes |

**Do not add libraries not in this list without verifying SiS availability first.**

---

## Development approach (two stages)

**Stage 1 — Local development:**
- Build and test all queries and chart functions locally
- Use `snowflake-connector-python` locally to connect to the same Snowflake account
- Run `streamlit run src/app.py` locally against real Gold data
- All queries must work correctly in this stage before Stage 2

**Stage 2 — SiS deployment:**
- Convert `snowflake-connector-python` queries to `snowflake.snowpark` session queries
- Deploy as SiS application in Snowflake UI
- Test all pages and filters in SiS environment
- Verify auto-refresh works in SiS context

**Local config (Stage 1 only):**
```ini
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=INDUSTRIAL_IOT_DEMO
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
DASHBOARD_REFRESH_INTERVAL_S=30
```

---

## Folder structure

```
wp6-analytical-dashboard/
  WP-BRIEF.md
  README.md
  requirements.txt          Local dev dependencies only
  .env.example              Stage 1 local dev env vars
  src/
    app.py                  Entry point: streamlit run src/app.py (local)
    pages/
      01_cycle_overview.py  Cycle overview table + row click
      02_cycle_detail.py    KPI cards + time-series chart
      03_efficiency.py      Bar chart + scatter + summary table
    queries.py              All SQL queries as typed functions (returns DataFrames)
    charts.py               Plotly chart builder functions
    filters.py              Sidebar filter component, returns filter state dict
    connection.py           Snowflake connection — local (connector) or SiS (snowpark)
    models.py               CycleSummary, EfficiencyRow dataclasses
  sis/
    app_sis.py              SiS entry point (snowpark session, no connector)
    README_SIS.md           SiS deployment instructions
  tests/
    test_queries.py         Run against test Snowflake schema with fixture data
    test_charts.py          Verify chart functions return valid Plotly figures
    conftest.py             Fixtures loading from contracts/seed-data/
```

---

## Chart specifications

### Time-series chart (cycle detail)

```
X-axis:  Elapsed cycle time (minutes)
Y-axis left:  Temperature (°C) — line, colour: #E84545
              Vacuum (mbar) — line, colour: #3D5A80
Y-axis right: Moisture (ppm) — line, colour: #98C1D9
              Moisture target threshold — dashed horizontal, colour: #E84545

Annotations:
  - "Threshold met" vertical line at the point moisture crosses target
  - Cycle standard duration vertical line (from MaterialMaster)
```

### Efficiency bar chart

```
X-axis: Material description
Y-axis: Duration (minutes)
Series 1: Standard cycle time (grey bar)
Series 2: Average actual duration (coloured bar — green if ≤ standard, amber/red if over)
```

### Efficiency scatter

```
X-axis: Actual duration (minutes)
Y-axis: Final moisture ppm
Colour: Material type
Symbol: ● = spec met, ✗ = spec not met
Reference lines: horizontal = target moisture (per material, if single material selected)
```

---

## Definition of Done

- [ ] Standard DoD (see SDLC.md Phase 3)
- [ ] Stage 1: all pages render correctly against real WP5 Gold data locally
- [ ] Stage 2: SiS app deployed and accessible in Snowflake
- [ ] Cycle overview table renders with correct seed data (20 historical cycles visible)
- [ ] Cycle detail view shows correct KPIs and time-series chart for at least 3 historical cycles
- [ ] Efficiency analysis page renders correctly with all 4 material types
- [ ] All sidebar filters work correctly across all pages
- [ ] Auto-refresh picks up a new cycle within 60s of it appearing in Gold
- [ ] No hardcoded data — all content from Snowflake
- [ ] Characteristic drying curve visible in cycle detail time-series (moisture decay shape correct)

## Open items

- [ ] Confirm SiS auto-refresh approach: `st.fragment` (Streamlit 1.33+) vs `streamlit-autorefresh` package availability in SiS
- [ ] Confirm unified visual theme with WP7 — colour palette to be agreed before WP7 starts
- [ ] Confirm whether WP7 embeds SiS via iframe or links out to it

## Session handover notes

> *To be filled by the agent at the end of each session.*
