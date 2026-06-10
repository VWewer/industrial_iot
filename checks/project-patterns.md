# Project Patterns -- Golden Reference

> **Purpose:** This file extracts the settled, battle-tested patterns from WP1 (sensor sim) and WP4 (SAP mock). Every new WP must be checked against this reference at Phase 1 kickoff and again at Phase 3 DoD before proceeding to Phase 4.
>
> This is the Level 3 harmony check (see AI-DEV.md Section 15). It is not exhaustive -- it covers the patterns that caused real problems or that are easy to diverge on silently.
>
> **Source WPs:** WP1 (wp1-sensor-sim/src/) and WP4 (wp4-sap-mock/src/) -- both Phase 4 complete as of 2026-06-03.

---

## P-01 -- Module structure

Every WP follows this layout. Do not invent new top-level files.

```
wp{n}-{name}/
  src/
    main.py           # entry point only -- no business logic here
    {noun}.py         # one module per logical concern (publisher, simulator, api)
    models.py         # all Pydantic models and dataclasses
    exceptions.py     # custom exceptions (if WP has > 2 failure modes)
  tests/
    test_{noun}.py    # mirrors src/ structure
    integration/      # tests requiring live external services
  requirements.txt    # pinned exact versions (==)
  .env.example        # all env vars, no secrets
  pytest.ini          # register custom marks; suppress library-level warnings
  README.md           # run instructions, env vars, sample output
  WP{n}-BRIEF.md      # scope, contracts, DoD, session handover
```

**Check:** Does the new WP have all of these? Is each file doing one thing?

---

## P-02 -- main.py is an entry point only

`main.py` reads env vars, wires up components, and starts services. It contains no business logic.

```python
# correct pattern (from WP1 main.py)
def main() -> None:
    broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
    publisher = SensorPublisher(broker_host=broker_host, ...)
    publisher.connect()
    simulator = _build_simulator(publisher, compression, interval_s)
    init_app(simulator)
    api_thread = threading.Thread(target=uvicorn.run, ...)
    api_thread.start()
    api_thread.join()
```

**Check:** Does `main.py` contain any logic beyond wiring? If yes, move it to the appropriate module.

---

## P-03 -- Environment variables

All config from env vars via `python-dotenv`. No hardcoded values in source.

```python
# correct pattern
load_dotenv()
broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
api_port = int(os.getenv("CONTROL_API_PORT", "8000"))
```

`.env.example` must document every variable:
```ini
MQTT_BROKER_HOST=localhost     # MQTT broker hostname
MQTT_BROKER_PORT=1883          # MQTT broker port
CONTROL_API_PORT=8080          # FastAPI port (use 8080 on Windows -- 8000 may be excluded)
```

**Check:** Is every configuration value in `.env.example`? Are types cast on load (int, float)?

---

## P-04 -- Logging format

Use Python `logging`, not `print`. Always pass context as `extra={}`.

```python
# correct -- structured, searchable
log.info("MQTT broker connected", extra={"host": self._broker_host, "port": self._broker_port})
log.info("State transition: WARMING -> DRYING", extra={"order_id": config.order_id})
log.warning("MQTT broker disconnected", extra={"rc": str(reason_code)})
log.error("Failed to connect to MQTT broker: %s", exc)

# wrong -- no context, not searchable
log.info("Connected")
print("State changed")
```

Log levels:
- `DEBUG`: per-reading / per-tick noise (default off)
- `INFO`: state transitions, service start/stop, cycle events
- `WARNING`: degraded operation (reconnect, retry)
- `ERROR`: failures with impact

**Check:** Every state transition logged at INFO with order_id in extra? No print() statements? No bare log.error("something") without context?

---

## P-05 -- Custom exceptions

Define in `exceptions.py`. Raise specific exceptions, not generic ones.

```python
# exceptions.py -- correct pattern (from WP1)
class MQTTConnectionError(Exception):
    """Raised when the MQTT broker cannot be reached on startup."""

class CycleAlreadyRunningError(Exception):
    """Raised when start() is called while a cycle is active."""

class NoCycleActiveError(Exception):
    """Raised when stop() or a cycle operation is called with no active cycle."""
```

FastAPI endpoints convert custom exceptions to HTTP responses:
```python
# correct pattern
try:
    simulator.start(config)
except CycleAlreadyRunningError:
    raise HTTPException(status_code=409, detail="Cycle already running")
```

**Check:** Are all distinct failure modes named in exceptions.py? No bare `raise Exception("message")`? HTTP status codes correct (409 conflict, 422 validation, 404 not found)?

---

## P-06 -- FastAPI health endpoint

Every WP with a REST API must have `/health`. Returns 200 with a JSON body.

```python
# correct pattern (from WP4)
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "wp4-sap-mock"}
```

For WPs with state (WP1, WP2, WP3), include current state:
```python
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "wp1-sensor-sim",
        "simulator_state": simulator.state.value if simulator else "not_initialised",
    }
```

**Check:** Does `/health` return 200 even when the main logic is idle? Is the response flat JSON (no nesting)?

---

## P-07 -- Pydantic v2 models

Use Pydantic v2. Field validators use `@field_validator`. No `@validator` (v1 pattern).

```python
# correct -- Pydantic v2 (from WP1 control_api.py)
from pydantic import BaseModel, field_validator

class StartRequest(BaseModel):
    order_id: str
    oven_id: str
    target_moisture_ppm: float = 300.0

    @field_validator("order_id")
    @classmethod
    def order_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("order_id must not be empty")
        return v

# wrong -- Pydantic v1 pattern
from pydantic import validator
@validator("order_id")  # deprecated
def check(cls, v): ...
```

**Check:** All validators use `@field_validator` + `@classmethod`? No `@validator`?

---

## P-08 -- Timestamps

ISO 8601 UTC with millisecond precision everywhere.

```python
# correct -- always includes milliseconds
from datetime import datetime, timezone

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
# produces: "2026-06-03T15:42:30.077Z"
```

Validators must accept optional milliseconds:
```python
# correct regex
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

# wrong -- rejects milliseconds
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
```

**Check:** Does every timestamp-producing function use the pattern above? Does every timestamp-validating regex include `(\.\d+)?`?

---

## P-09 -- JSON response envelope

No envelope. Flat JSON. Lists are JSON arrays at the root.

```json
// correct -- flat, no wrapper
{"order_id": "ORD-2026-00001", "status": "RELEASED", "material_id": "MAT-0001"}

// wrong -- unnecessary envelope
{"data": {"order_id": "...", ...}, "meta": {"status": 200}}
{"result": [...], "count": 5}
```

Lists: return a JSON array directly, not `{"items": [...]}`.

**Check:** Do all endpoints return flat JSON? No `data`, `result`, `payload` wrappers?

---

## P-10 -- Field naming

snake_case in all JSON payloads. No camelCase, no kebab-case.

```json
// correct
{"order_id": "ORD-2026-00001", "sensor_type": "temperature", "timestamp_opc": "..."}

// wrong
{"orderId": "...", "sensorType": "...", "timestampOpc": "..."}
{"order-id": "...", "sensor-type": "..."}
```

Enum values: lowercase in MQTT and REST payloads.
```json
// correct
{"sensor_type": "temperature", "quality": "Good", "state": "idle"}

// wrong (except SAP-originated status fields which are UPPERCASE by domain convention)
{"sensor_type": "TEMPERATURE"}
```

**Check:** All JSON field names snake_case? All enum values lowercase (except SAP status fields)?

---

## P-11 -- pytest.ini required

Every WP that uses a custom pytest mark must declare it. Every WP using FastAPI TestClient must suppress the Starlette deprecation warning.

```ini
[pytest]
asyncio_mode = strict

markers =
    integration: marks tests that require a running external service (deselect with -m "not integration")

filterwarnings =
    ignore::starlette.exceptions.StarletteDeprecationWarning
```

**Check:** Does `pytest tests/ -v` exit with 0 warnings? Is pytest.ini present at WP root?

---

## P-12 -- Python source is ASCII-only

No em-dashes, Unicode arrows, degree signs, or other non-ASCII in `.py` files.
Docstrings and comments use: `--` not `--`, `->` not `->`, `degC` not `degC`.

Quick check:
```powershell
Get-Content src\*.py | Select-String -Pattern '[^\x00-\x7F]'
```

Markdown docs may use UTF-8 (arrows in architecture diagrams, emoji in status tables are fine).

**Check:** Zero matches from the command above?

---

## P-13 -- Service port assignments

All service ports are defined in **`.env.example` at the project root** (machine-readable) and in **`architecture_handover.md` Section 0a ports table** (human-readable). These are the single source of truth. Every `.env.example`, brief, README, and `docker-compose.yml` must cite these values exactly.

**Canonical port table:**

| Service | Port | Env var |
|---|---|---|
| Mosquitto MQTT broker | 1883 | `MQTT_BROKER_PORT` |
| WP1 control API (Windows native) | **8080** | `CONTROL_API_PORT` |
| WP1 control API (Docker) | 8000 | `CONTROL_API_PORT` |
| WP2 SIMATIC mock | 8001 | `SIMATIC_API_PORT` |
| WP3 Mendix mock | 8002 | `MENDIX_API_PORT` |
| WP4 SAP mock | 8003 | `SAP_API_PORT` |
| WP5 Snowflake layer | 8005 | `WP5_API_PORT` |
| WP7 Unified cockpit | 8501 | `COCKPIT_PORT` |

WP6 (Streamlit in Snowflake) runs inside Snowflake -- no local port.

**Check:** When implementing or reviewing a new WP, verify every hardcoded URL and port reference against this table. Any deviation must be an explicit documented exception (e.g., WP1 using 8080 on Windows vs 8000 in Docker -- both are correct, for different environments).

**What caused port drift (2026-06-10):** WP5-BRIEF.md used 8004 for SAP_API_URL, and WP7-BRIEF.md had all WP URLs shifted by +1. These were caught by a manual audit. P-13 makes this a Phase 1 gate check so future WPs are verified before any code is written.

---

## Summary checklist (Level 3 harmony check)

Run at Phase 1 kickoff and Phase 3 DoD for every new WP. Takes ~10 minutes.

| # | Check | Source pattern |
|---|---|---|
| P-01 | Module structure matches template | WP1, WP4 |
| P-02 | main.py is wiring only | WP1 |
| P-03 | All config from env vars, .env.example complete | WP1, WP4 |
| P-04 | Logging: structured extra={}, correct levels, no print() | WP1, WP4 |
| P-05 | Custom exceptions named, HTTP codes correct | WP1, WP4 |
| P-06 | /health endpoint returns 200 flat JSON | WP4 |
| P-07 | Pydantic v2: @field_validator + @classmethod | WP1, WP4 |
| P-08 | Timestamps: ISO 8601 UTC with ms, validator regex correct | WP1 |
| P-09 | Flat JSON responses, no envelope | WP4 |
| P-10 | snake_case fields, lowercase enums | WP1, WP4 |
| P-11 | pytest.ini present, 0 warnings | WP1 |
| P-12 | Python source ASCII-only | WP1 |
| P-13 | All service URLs match canonical port table in .env.example + architecture_handover.md | .env.example (root) |
