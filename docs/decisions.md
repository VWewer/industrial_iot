# Architecture Decision Records

## ADR-001: DuckDB as local Snowflake substitute
Date: 2024-11-15
Status: **Superseded by ADR-005**

### Context
The target architecture uses Snowflake as the analytical hub. A Snowflake account requires cloud setup, credentials, and network access — which adds friction for local development, demo portability, and agent-based execution.

### Decision
Use DuckDB as the local substitute for Snowflake. The schema (`contracts/snowflake-schema.sql`) is written to be compatible with both DuckDB and Snowflake SQL dialects.

### Consequences
- Demo runs fully locally with no cloud dependencies
- Snowflake-specific features (Snowpipe, time-travel, clustering) not demonstrated
- Superseded once a Snowflake account became available — see ADR-005

---

## ADR-002: FastAPI for all mock REST services
Date: 2024-11-15
Status: Accepted

### Context
WP2, WP3, and WP4 each require a REST API service. Options considered: Flask, FastAPI, Django REST Framework.

### Decision
FastAPI for all mock services. Reasons: automatic OpenAPI schema generation (useful for demonstrating OData-style interfaces), async support (relevant for WP3 which makes outbound HTTP calls), type annotations align with project code standards, lightweight.

### Consequences
- All mock services use uvicorn as the ASGI server
- OpenAPI docs available at `/docs` for each service (useful for demo and debugging)
- Pydantic models required for request/response bodies — adds a small typing overhead but improves correctness

---

## ADR-003: Single-oven scope for WP1–WP3
Date: 2024-11-15
Status: Accepted

### Context
The real plant has multiple ovens. Simulating multiple ovens multiplies complexity in WP1, WP2, WP3, and WP7 without adding architectural insight beyond what a single oven demonstrates.

### Decision
Scope WP1–WP3 to a single oven instance (`oven-01`, plant `regensburg`). The architecture is designed to scale horizontally — multiple WP1/WP2 instances with different `OVEN_ID` env vars would extend naturally — but this is not implemented in the demo.

### Consequences
- WP1 publishes to a single set of MQTT topics
- WP2 maintains historian for one oven
- WP4 seed data has one active order at a time
- WP7 cockpit is designed around one oven's workflow

---

## ADR-004: MQTT over direct REST for sensor ingestion
Date: 2024-11-15
Status: Accepted

### Context
Sensor data from WP1 could be pushed directly to WP5 via REST, or via MQTT broker. MQTT adds a dependency (Mosquitto broker) but more accurately represents the real architecture where SIMATIC publishes to an MQTT broker.

### Decision
Use MQTT with a local Mosquitto broker. The broker is project-level infrastructure (started via docker-compose, not owned by any single WP). WP1 publishes; WP2 and WP5 both subscribe.

### Consequences
- Mosquitto must be running before WP1, WP2, or WP5 can start
- Adds one infrastructure dependency to the project setup
- Accurately represents the real architectural pattern
- WP2 and WP5 receive the same sensor stream independently (fan-out for free)

---

## ADR-005: Real Snowflake replaces DuckDB for WP5 and WP6
Date: 2026-06-01
Status: Accepted
Supersedes: ADR-001

### Context
A Snowflake account is available. The original rationale for DuckDB (no cloud account) no longer applies. Using real Snowflake enables Snowpipe for streaming ingestion and Streamlit in Snowflake (SiS) for the dashboard — both of which are core portfolio claims that cannot be demonstrated with DuckDB.

### Decision
WP5 targets real Snowflake. Bronze ingestion uses Snowpipe (sensor stream) and the Snowflake Python connector (MES events, SAP batch). Silver and Gold transforms run as scheduled SQL via the Python connector. DuckDB is removed from WP5 scope.

WP6 deploys as a Streamlit in Snowflake (SiS) application, co-located with the Gold layer. No external Streamlit host, no `snowflake-connector-python` dependency in WP6 (native query instead).

### Consequences
- WP5 brief updated: DuckDB removed, Snowflake connector + Snowpipe added
- WP6 brief updated: SiS deployment, native query instead of connector
- WP7 (unified cockpit) analytics panel: embeds or links to SiS rather than importing WP6 Streamlit code
- Local development of WP6 requires Snowflake account credentials in `.env`
- `DUCKDB_PATH` env var removed from WP5 and WP6 configuration
- ADR-001 superseded; `contracts/snowflake-schema.sql` remains the schema reference (already Snowflake-native)
- WP5 Open item resolved: query surface is Snowflake SQL via Python connector (not DuckDB API)

---

## ADR-006: Streamlit in Snowflake (SiS) as dashboard host
Date: 2026-06-01
Status: Accepted

### Context
WP6 analytical dashboard needs a deployment target. Options: standalone Streamlit app (local or Streamlit Cloud), or Streamlit in Snowflake (SiS). Given that WP5 uses real Snowflake and the architecture argument is "Snowflake as single analytical hub," hosting the dashboard inside Snowflake is the architecturally coherent choice.

### Decision
WP6 deploys as a Streamlit in Snowflake (SiS) application. The app queries the Gold layer via native Snowflake SQL — no external connector, no credentials to manage in the app.

### Consequences
- Dashboard development happens in two stages: develop and test queries locally (Python + snowflake-connector-python), then deploy as SiS worksheet
- SiS Python environment is slightly restricted — verify library availability before adding dependencies
- WP7 unified cockpit links to or embeds the SiS dashboard rather than importing WP6 Python code
- Portfolio claim strengthened: "built and deployed the analytical layer natively in Snowflake"

---

## ADR-007: No user authentication in unified cockpit
Date: 2026-06-01
Status: Accepted

### Context
The unified cockpit (WP7) could implement persona-based login to distinguish machine operator, production operator, and process engineer views. This would require authentication infrastructure (user store, session management) and switching logic.

### Decision
No authentication. WP7 uses a tab/panel layout where each panel implies a persona. The panel boundary is the persona boundary. No login, no role switching.

### Consequences
- Significantly reduces WP7 complexity
- Demo is freely accessible without credentials
- Personas are communicated by panel context rather than login state
- Appropriate for a portfolio demo; would not be appropriate for production

---

## ADR-008: Compressed time model for sensor simulation
Date: 2026-06-01
Status: Accepted

### Context
Real transformer drying cycles run 2–12 hours depending on transformer type. A live demo cannot run in real time — the demo would take hours. The cycle must be compressed to be demonstrable in a meeting.

### Decision
Default compression factor: 60× (1 real minute = 1 cycle hour). At this rate, a standard 4-hour cycle (MAT-0002, 240 minutes) completes in 4 real minutes. A full demo run (WF1 → WF4) takes approximately 12–15 real minutes.

Compression factor is configurable via `CYCLE_COMPRESSION_FACTOR` env var in WP1. The default of 60 is appropriate for live demos; a factor of 1 gives real-time simulation for testing.

### Consequences
- WP1 sensor publishing interval is 5 seconds real time (= 5 minutes of cycle time at 60×)
- Moisture decay curve must be parameterised by compressed cycle duration, not real duration
- WP7 elapsed time display must show cycle time (compressed), not wall clock time
- Seed historical data uses compressed timestamps for consistency
