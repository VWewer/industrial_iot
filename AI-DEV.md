# AI-DEV.md — AI-Assisted Development Methodology

> **Status:** v1.1 — June 2026  
> **Changes from v1.0:** Added Section 12 (End-of-Dev-Cycle Workflow), Section 13 (Debug and RCA Procedure), Section 14 (Known Issues and Learnings). Updated Session Close Protocol to mandate the full end-of-cycle sequence.  
> **Purpose:** Defines how AI agents (Claude Code, Claude chat) are used to implement this project. Covers session structure, prompt engineering for WP briefs, context handover discipline, and patterns that make agent sessions faster and more autonomous. Read alongside `SDLC.md` — this document covers the AI-specific layer; SDLC covers the delivery process.

---

## Table of Contents

1. [Core Principles](#1-core-principles)
2. [What Makes a Good Agent Task](#2-what-makes-a-good-agent-task)
3. [WP Brief as Agent Prompt](#3-wp-brief-as-agent-prompt)
4. [Session Open Protocol](#4-session-open-protocol)
5. [Session Close Protocol](#5-session-close-protocol)
6. [Context Handover Between Sessions](#6-context-handover-between-sessions)
7. [Mid-Session Contract Changes](#7-mid-session-contract-changes)
8. [Reusable Skills](#8-reusable-skills)
9. [Seed Data and Fixtures](#9-seed-data-and-fixtures)
10. [What Agents Do Well vs Badly](#10-what-agents-do-well-vs-badly)
11. [Prompt Patterns That Work](#11-prompt-patterns-that-work)
12. [End-of-Dev-Cycle Workflow](#12-end-of-dev-cycle-workflow)
13. [Debug and RCA Procedure](#13-debug-and-rca-procedure)
14. [Known Issues and Learnings](#14-known-issues-and-learnings)
15. [Three-Level Consistency Check](#15-three-level-consistency-check)

---

## 1. Core Principles

**Contracts before code.** Agents implement against contracts, not against assumptions. An agent that invents a schema because the contract was ambiguous will diverge from every other WP. Phase 0 (contracts) must be complete before any agent writes implementation code.

**Briefs are prompts.** The WP-BRIEF.md is the agent's system prompt. Its quality directly determines output quality. A vague brief produces vague code. A brief with exact field names, typed schemas, and explicit DoD checkboxes produces implementable code.

**One WP per session.** Do not ask an agent to implement multiple workpackages in one session. Context bleed between WPs produces inconsistent naming, silent schema divergences, and code that works in isolation but fails at the seam.

**Surface ambiguity early.** Agents must raise ambiguities at the start of a session, not mid-implementation. A mid-implementation discovery that requires a contract change is expensive. An upfront clarification question costs 30 seconds.

**Agents do not make architectural decisions.** If an agent encounters a decision point not covered by the brief, contracts, or ADRs — it stops and surfaces the question. It does not pick and proceed.

---

## 2. What Makes a Good Agent Task

Good agent tasks have:
- A single, clearly bounded output (one module, one endpoint, one transformation)
- All required inputs available in the session context (schema, upstream contract, example payload)
- An explicit, testable Definition of Done
- No dependency on runtime state from another WP that isn't mocked

Poor agent tasks:
- "Build WP5" (too large — decompose into ingestion, transforms, query API as separate tasks)
- "Make the dashboard look good" (no acceptance criterion)
- "Fix the integration" (requires knowing what's broken first)
- Tasks that require the agent to make decisions not in the brief

**Rule of thumb:** If you can't write a passing test for the output before the agent starts, the task is too vague.

---

## 3. WP Brief as Agent Prompt

Every `WP-BRIEF.md` is structured to serve as the agent prompt document. The structure is mandatory — do not reorder sections.

### Required sections (every WP brief)

```markdown
# WP{n} — {Name}

## Status
NOT STARTED | IN PROGRESS | COMPLETE | BLOCKED

## Role in the architecture
One paragraph. What this WP does and why it exists. No jargon not already defined in DOMAIN-MODEL.md.

## What this WP produces
Exact contract reference (e.g. Contract C2). Field names and types inline — do not just reference another file.

## What this WP consumes
Same — exact contract references with inline schema for anything this WP reads.

## Scope
### Must implement
Numbered list of concrete deliverables. Each item is testable.

### Out of scope
Explicit list. Prevents scope creep during agent sessions.

## Tech stack
Exact libraries and versions. No "or similar."

## Configuration
All env vars with example values and descriptions.

## Folder structure
Expected file tree. Agent fills this structure — does not invent its own.

## Definition of Done
Checkboxes. Agent self-evaluates before declaring complete.

## Open items
Unresolved questions that must be answered before the session proceeds.

## Session handover notes
Updated by the agent at session close. Format: date, what was done, what's in progress, blockers, next action.
```

### Inline schema discipline

Do not write "see interface-contracts.md for the schema." Write the schema inline in the brief. The agent's context window is finite — requiring it to mentally join across documents introduces errors. The contracts file is the source of truth; the brief is a denormalised copy for the agent's convenience. If the contract changes, update both.

**Good:**
```markdown
## What this WP produces
REST endpoint `GET /process-state/{oven_id}` returning:
```json
{
  "oven_id": "string",
  "order_id": "string | null",
  "status": "idle | running | cycle_complete | timeout",
  "temperature_degC": "float | null",
  "vacuum_mbar": "float | null",
  "moisture_ppm": "float | null",
  "cycle_elapsed_minutes": "float | null",
  "moisture_threshold_met": "boolean | null",
  "timestamp": "datetime (ISO 8601 UTC)"
}
```

**Bad:**
```markdown
## What this WP produces
Process state API — see contracts/interface-contracts.md C2 for details.
```

---

## 4. Session Open Protocol

**Every agent session starts with this sequence. No exceptions.**

### Context to provide (always)

1. `CONTRIBUTING.md` — code standards
2. `SDLC.md` — delivery process
3. `AI-DEV.md` — this document (agent methodology)
4. `DOMAIN-MODEL.md` — canonical schemas and workflows
5. `wp{n}/WP-BRIEF.md` — the specific WP being implemented
6. Relevant contract sections (inline or as attached file)
7. Status summary if continuing a previous session

### Opening statement to the agent

Use this template — adapt as needed:

```
We are implementing WP{n} ({name}) of the Industrial IoT Demo project.

Phase: {Phase 1 kickoff | Phase 2 implementation | Phase 3 DoD check | Phase 4 seam check}

Context documents provided:
- CONTRIBUTING.md (code standards)
- SDLC.md (delivery process)
- AI-DEV.md (agent methodology)
- DOMAIN-MODEL.md (canonical schemas)
- WP-BRIEF.md (scope and DoD for this WP)
- [any relevant contract sections]

{If continuing:} Session status: {paste from WP-BRIEF.md session handover notes}

Before writing any code:
1. Read all provided documents in full.
2. State which Phase this session is in.
3. List any ambiguities or missing information that would block implementation.
4. Confirm the exact deliverables you will produce this session.

Do not write implementation code until ambiguities are resolved.
```

### What to do if the agent skips straight to code

Stop it. Ask it to complete the session open protocol first. An agent that starts coding without confirming scope and surfacing ambiguities will produce output that requires rework.

---

## 5. Session Close Protocol

**Every agent session ends with the full End-of-Dev-Cycle Workflow (Section 12). No exceptions.**

### Agent responsibilities at session close

1. Run the complete end-of-cycle workflow from Section 12.

2. Update `WP-BRIEF.md` → `Session handover notes` with:
   - Date and session number
   - What was completed this session (specific files, functions, tests)
   - What is in progress (partially complete, needs continuation)
   - Blockers (unresolved questions, missing context, contract gaps)
   - Exact next action for the next session (first thing to do, not a summary)

3. Run `pytest tests/` and confirm 0 warnings, all passing. If failing, apply the RCA procedure (Section 13) before declaring the session closed.

4. Confirm no secrets or `.env` files are staged for commit.

5. Confirm all new files follow the folder structure in the WP brief.

6. Update `architecture_handover.md` delivery tracker (Section 0a) to reflect current phase status.

### Human responsibilities at session close

1. Review the session handover notes before closing.
2. If a contract was changed, confirm it was updated in `contracts/interface-contracts.md` AND in all affected WP briefs.

---

## 6. Context Handover Between Sessions

Agents have no memory between sessions. Every session starts cold. The only continuity mechanism is the written record in `WP-BRIEF.md` → Session handover notes.

### Session handover note format

```markdown
## Session handover notes

### Session {n} — {YYYY-MM-DD}
**Status at close:** IN PROGRESS

**Completed this session:**
- Implemented `src/ingestion/mqtt_subscriber.py` — subscribes to `factory/#`, writes to bronze_sensor_readings
- Implemented `src/db.py` — DuckDB connection + schema init from `contracts/snowflake-schema.sql`
- Tests: `test_ingestion.py` passes (4/4), `test_db.py` passes (2/2)

**In progress:**
- `src/ingestion/mes_webhook.py` — FastAPI endpoint scaffolded, write-to-DB not yet implemented

**Blockers:**
- None

**Next session — first action:**
Complete `mes_webhook.py`: implement the `POST /events` handler writing to `bronze_mes_events`. Schema is in DOMAIN-MODEL.md Section 1.4. After that, move to `src/ingestion/sap_puller.py`.
```

### What happens if handover notes are missing

If session handover notes are empty or missing, the agent at the next session must:
1. Read all files in `src/` and `tests/` to reconstruct current state
2. Run `pytest tests/` to establish baseline
3. Write a state summary before proceeding

This costs 10–15 minutes. Write the handover notes.

---

## 7. Mid-Session Contract Changes

If an agent discovers during implementation that a contract needs to change (schema field missing, type wrong, endpoint not matching behaviour needed):

**Stop. Do not implement a workaround.**

Protocol:
1. Agent surfaces the issue explicitly: "Contract C{n} specifies field X as string, but WP{m} requires it to be an enum for correct filtering. This needs a contract change."
2. Human reviews and approves the change.
3. Update `contracts/interface-contracts.md` first.
4. Update `DOMAIN-MODEL.md` if the affected object is defined there.
5. Identify all WPs affected by the change — update their briefs.
6. Resume implementation.

**Never silently implement a diverging schema.** The seam check in Phase 4 will catch it — but the cost of fixing a divergence at integration is 10× the cost of fixing it at the contract level.

---

## 8. Skills

Two categories of skills are available: **global skills** (installed in `~/.claude/skills/`, available in every project) and **project skills** (implementation scaffolds specific to this codebase). Both are used throughout the SDLC.

---

### 8a. Global skills — installed

These skills are installed globally and activate automatically when relevant context is present. They can also be invoked explicitly. The agent will prompt you at appropriate workflow points; you can also invoke any of them directly at any time.

| Skill | Invoke | When the agent uses it |
|---|---|---|
| **python-pro** | mention "python" patterns | Whenever writing or reviewing Python modules — typing, async, dataclasses |
| **fastapi-expert** | mention "FastAPI" | WP1 control API, WP2, WP3, WP4 — routing, Pydantic v2, lifespan, async |
| **api-designer** | mention "contract" or "endpoint" | Contract change reviews, new endpoint design |
| **sql-pro** | mention "SQL" or "Snowflake" | WP5 DDL, Gold layer transforms, window functions |
| **database-optimizer** | mention "query" or "index" | WP5/WP6 Snowflake query tuning |
| **test-master** | mention "test strategy" | At Phase 3 DoD — coverage gaps, integration test patterns |
| **code-reviewer** | `/review` or Phase 4 seam check | Before merging any WP branch to main |
| **devops-engineer** | mention "Docker" or "CI" | Dockerfile reviews, docker-compose changes |
| **monitoring-expert** | mention "logging" or "observability" | Logging discipline, structured logging patterns |
| **debugging-wizard** | any test failure | Systematic root-cause analysis when tests fail or services misbehave |
| **architecture-designer** | mention "ADR" or design question | Any structural decision — new ADR, approach selection |
| **secure-code-guardian** | any auth or input handling | Security review on API endpoints, input validation |
| **the-fool** | `/grill-me` | Stress-test any plan or design decision before committing to it |

**Special skills already installed:**
- `/grill-me` — relentless structured interview to stress-test a plan (use before WP kickoffs)

---

### 8b. Skill workflow map — when the agent prompts you

The agent will suggest or automatically apply a skill at these trigger points:

| SDLC moment | Agent action |
|---|---|
| **Phase 1 kickoff** (any WP) | Prompt: *"Want to /grill-me on the design before we code?"* |
| **Phase 2 — writing Python modules** | Auto-apply `python-pro` + `fastapi-expert` standards |
| **Phase 2 — contract question** | Auto-apply `api-designer` — surface trade-offs before deciding |
| **Phase 2 — any test failure** | Auto-apply `debugging-wizard` — systematic diagnosis before fixing |
| **Phase 3 DoD check** | Prompt: *"Run test-master review for coverage gaps?"* |
| **Phase 4 seam check** | Auto-invoke `code-reviewer` checklist before merge |
| **Phase 4 — SQL/Snowflake work** | Auto-apply `sql-pro` + `database-optimizer` |
| **Any Dockerfile / compose change** | Auto-apply `devops-engineer` standards |
| **Any new ADR** | Auto-apply `architecture-designer` template |
| **Pre-WP7 integration** | Prompt: *"Run /grill-me on the integration plan?"* + `secure-code-guardian` review |

---

### 8c. Project-specific skill scaffolds

These are implementation patterns specific to this codebase. Create them as WPs are completed — they encode decisions already made so future WPs don't re-litigate them.

**`skills/fastapi-mock-service/`** ← create after WP2
Pattern for WP2, WP3: FastAPI app structure, Pydantic models, uvicorn entrypoint, health endpoint, `.env` loading, logging setup.

**`skills/mqtt-subscriber/`** ← create after WP2
Pattern for WP2 and WP5: paho-mqtt subscriber, topic filter, message handler, error handling on malformed payloads.

**`skills/snowflake-ingestion/`** ← create after WP5
Pattern for WP5 Bronze ingestion: `snowflake-connector-python` setup, staging area write, Snowpipe trigger, error handling.

**`skills/streamlit-page/`** ← create after WP6
Pattern for WP6 and WP7: page structure, Snowflake query function, Plotly chart builder, sidebar filter, auto-refresh.

### How to create a new project skill

After completing a WP, if its pattern is reusable:
1. Extract the scaffold to `skills/{pattern-name}/`
2. Write `SKILL.md` explaining: what it covers, how to use it, what to customise per WP
3. Include a minimal working example
4. Reference the skill in the relevant WP briefs

---

## 9. Seed Data and Fixtures

Seed data is defined in `DOMAIN-MODEL.md` Section 8 and lives in `contracts/seed-data/`. It is the only source of reference data for development and testing.

### Rules for agents using seed data

- Never invent data. If seed data doesn't cover a case needed for testing, add to `contracts/seed-data/` and note the addition in the session handover.
- Seed data field names must match `DOMAIN-MODEL.md` exactly. No aliases, no abbreviations.
- When writing tests, load fixtures from `contracts/seed-data/` — do not hardcode test data inline in test files.

### Fixture pattern for unit tests

```python
# tests/conftest.py
import json
import pytest
from pathlib import Path

SEED_DATA_PATH = Path(__file__).parent.parent.parent / "contracts" / "seed-data"

@pytest.fixture
def production_orders():
    with open(SEED_DATA_PATH / "production_orders.json") as f:
        return json.load(f)

@pytest.fixture
def material_masters():
    with open(SEED_DATA_PATH / "material_masters.json") as f:
        return json.load(f)
```

---

## 10. What Agents Do Well vs Badly

### Agents do well at

- Implementing a well-specified module with a clear interface contract
- Writing unit tests for functions they just wrote
- Following a folder structure and naming convention consistently
- Generating realistic seed/fixture data from a schema
- Refactoring code to match standards (typing, logging, error handling)
- Writing docstrings and README sections
- Schema validation scripts

### Agents do badly at

- Deciding between two plausible architectural approaches (ask a human)
- Maintaining consistency across multiple files edited in the same session without re-reading them
- Catching their own logical errors in domain-specific business logic (test coverage is the guard)
- Long sessions (>60–90 min) — context quality degrades; prefer more shorter sessions
- Tasks with no clear endpoint — always give a specific DoD

### Session length guidance

| Task type | Recommended session length |
|---|---|
| Single module (< 200 lines) | 20–40 min |
| Full WP (simple: WP4 SAP mock) | 60–90 min, one session |
| Full WP (complex: WP5 data layer) | 3–4 sessions of 60 min |
| DoD check + fixes | 30 min |
| Phase 4 seam check | 30–45 min |

---

## 11. Prompt Patterns That Work

### Asking for an implementation

```
Implement [module name] in [file path].

It must:
1. [Specific behaviour 1]
2. [Specific behaviour 2]
3. [Specific behaviour 3]

Input schema: [paste exact schema]
Output schema: [paste exact schema]
Error handling: [specific cases and what to do]

Write the implementation, then write the unit tests in tests/test_{module}.py.
After writing both, run pytest tests/test_{module}.py and show me the output.
```

### Asking for a DoD check

```
We are at Phase 3 (DoD check) for WP{n}.
Read the DoD checklist in WP-BRIEF.md.
For each checkbox:
1. State whether it passes or fails.
2. If it fails, state exactly what is missing and what needs to be done.
Do not fix anything yet — produce the checklist assessment first.
```

### Asking for a seam check

```
We are at Phase 4 (seam check) for WP{n} as a [producer/consumer].
The contract this WP [produces/consumes] is C{n} — [description].
Contract spec: [paste exact schema]

Run the WP and capture a sample output.
Validate the sample against the contract spec field by field:
- Field name: correct / MISMATCH
- Type: correct / MISMATCH  
- Required field present: yes / MISSING
- Value in expected range: yes / OUT OF RANGE

Report mismatches. Do not fix them yet.
```

### Asking for a session handover

```
We are closing this session.
Update WP-BRIEF.md -> Session handover notes with:
1. Everything completed this session (file names, function names, test count)
2. What is in progress
3. Any blockers or open questions
4. The exact first action for the next session

Then run the end-of-cycle workflow (AI-DEV.md Section 12) and report the result.
```

---

## 12. End-of-Dev-Cycle Workflow

**This sequence runs at the end of every phase (P2, P3, P4) and at every session close. It is mandatory — not optional. The session is not done until all steps are green.**

```
[1] Run tests
      |
      +-- FAIL --> [Debug: Section 13 RCA procedure] --> fix --> back to [1]
      |
      OK
      |
[2] Zero warnings
      |
      +-- WARN --> diagnose root cause --> fix or suppress with justification --> back to [1]
      |
      OK
      |
[3] Update documentation
      |  - WP-BRIEF.md session handover notes
      |  - WP README.md (if running instructions changed)
      |  - architecture_handover.md delivery tracker (Section 0a)
      |  - AI-DEV.md Section 14 (if a new issue or pattern was discovered)
      |
[4] Stage and review
      |  git status -- confirm no .env / secrets staged
      |  git diff --stat -- sanity-check what changed
      |
[5] Commit
      |  Format: wp{n}: <imperative verb> <what>
      |  Body: what changed, why, test result
      |
[6] Push to WP branch
      |  git push origin wp{n}/{branch}
      |
[7] If Phase 4 complete: merge to main
```

### Step 3 documentation checklist

For every session close, tick off before committing:

- [ ] `WP-BRIEF.md` session handover section updated (date, what done, next action)
- [ ] `architecture_handover.md` §0a delivery tracker updated
- [ ] `docs/delivery-plan.md` "Where we are right now" table updated (WP status, milestone progress)
- [ ] WP `README.md` reflects current running instructions (ports, env vars, OS quirks)
- [ ] Any new issue or recurring pattern added to Section 14 of this file
- [ ] No Docker-only instructions left if the service also runs natively
- [ ] Sample output in README matches actual live output (not invented)

### Best practices enforced at every commit

The agent checks these before every commit. If any fail, fix before committing.

| Check | Rule |
|---|---|
| Timestamps | ISO 8601 UTC with millisecond precision: `YYYY-MM-DDTHH:MM:SS.mmmZ` |
| Field names | snake_case throughout (no camelCase, no kebab-case in JSON payloads) |
| Enum values | lowercase strings in MQTT/REST payloads; UPPERCASE only in SAP-originated status fields |
| Numeric precision | sensor values rounded to 3 d.p. (`round(value, 3)`) |
| Character set | ASCII-only in all source files, config files, and JSON payloads; no smart quotes, em-dashes, or non-ASCII symbols |
| Port conflicts | Never hardcode port 8000 on Windows without noting the exclusion risk; use env var override |
| pytest warnings | `pytest tests/ -v` must exit with 0 warnings before any commit |
| No secrets staged | `.env` files always in `.gitignore`; never staged |
| Commit message | `wp{n}: imperative verb what` -- body explains why and cites test result |

---

## 13. Debug and RCA Procedure

**Apply this procedure every time a test fails or a seam check finds a mismatch. Never fix a bug without first documenting it.**

### Step 1 — Reproduce

Run the failing test in isolation and capture the full output:

```bash
pytest tests/test_foo.py::TestBar::test_baz -v --tb=long 2>&1 | tee /tmp/fail.txt
```

Confirm the failure is deterministic (not a flaky timing issue). If flaky, note that explicitly.

### Step 2 — Document the symptom

Before touching any code, write down:

```
Symptom: <exact error message or assertion failure>
Test:     <test file and test name>
Observed: <what the code actually did>
Expected: <what it should have done>
Scope:    <is this isolated to one function, or does it affect multiple tests?>
```

### Step 3 — Root cause analysis

Work backwards from the symptom. For each hypothesis, state it explicitly and test it:

```
Hypothesis 1: <what might cause this>
  Evidence for: <observation>
  Evidence against: <observation>
  Test: <how to confirm or rule out>

Hypothesis 2: ...
```

**Do not fix until you have identified the root cause.** A fix applied to a symptom without understanding the cause will recur or produce a different failure.

### Step 4 — Fix

Fix only the root cause. Do not refactor surrounding code during a bug fix. Do not add error handling for scenarios that are not part of the root cause.

### Step 5 — Verify

Re-run the full test suite (not just the failing test) to confirm no regressions:

```bash
pytest tests/ -v
```

All tests must pass, zero warnings.

### Step 6 — Document in Section 14

Add the issue, root cause, and fix pattern to Section 14 (Known Issues and Learnings) so future sessions don't repeat the diagnosis.

### Common root cause categories

| Category | Signal | First thing to check |
|---|---|---|
| Schema mismatch | Validator fails on field format | Compare field in contract vs field produced by code |
| Port conflict | `[WinError 10013]` on bind | `netstat -ano | Select-String ":PORT"` -- use env var override |
| Missing pytest config | `PytestUnknownMarkWarning` | Add marker to `pytest.ini` markers section |
| Library deprecation warning | `DeprecationWarning` from third-party | Read warning source; suppress with `filterwarnings` if not caused by our code |
| Timestamp format mismatch | Regex match fails | Confirm whether producer includes milliseconds; adjust regex to `(\.\d+)?` |
| Thread/async timing | Test passes in isolation, fails in suite | Isolate with `pytest -p no:randomly` or add `time.sleep` only as last resort |

---

## 14. Known Issues and Learnings

This section accumulates confirmed bugs, recurring patterns, and environment-specific gotchas discovered during development. Update it whenever a new issue is found and fixed. Never delete entries -- mark them resolved instead.

---

### KI-001 -- Timestamp format: milliseconds vs seconds

**Status:** Resolved (2026-06-03, WP1 Phase 4)

**Symptom:** `contracts/validators/validate_c1_mqtt.py` rejected valid timestamps from the WP1 publisher with `timestamp_opc: must be ISO 8601 UTC string`.

**Root cause:** The validator's `ISO_RE` regex was `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` (no milliseconds). The C1 contract example explicitly shows `"2026-06-03T08:32:14.521Z"` (milliseconds), and `_utc_now()` in `publisher.py` always emits millisecond precision.

**Fix:** Updated regex to `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$`.

**Rule going forward:** All timestamp fields are ISO 8601 UTC with millisecond precision (`YYYY-MM-DDTHH:MM:SS.mmmZ`). Validators must accept the optional fractional seconds group `(\.\d+)?`. Do not write validators with second-only precision unless the contract explicitly prohibits milliseconds.

---

### KI-002 -- Windows port 8000 excluded from dynamic port range

**Status:** Documented (2026-06-03, WP1 Phase 4)

**Symptom:** `[WinError 10013] an attempt was made to access a socket in a way forbidden by its access permissions` when WP1 tries to bind on `0.0.0.0:8000`.

**Root cause:** Windows reserves certain TCP port ranges (viewable via `netsh int ipv4 show excludedportrange protocol=tcp`). Port 8000 is included in the excluded range on this machine (PID 4 / System holds it).

**Fix:** Set `CONTROL_API_PORT=8080` (or any free port) before starting any WP on this machine. All WP ports are driven by env vars -- never assume port 8000 is available on Windows.

**Rule going forward:** Never hardcode `8000` as a default in documentation examples. Always show the env var override. Document the Windows exclusion risk in every WP README.

---

### KI-003 -- pytest.mark.integration not registered

**Status:** Resolved (2026-06-03, WP1 debug)

**Symptom:** `PytestUnknownMarkWarning: Unknown pytest.mark.integration` every test run.

**Root cause:** No `pytest.ini` existed in `wp1-sensor-sim/`. Pytest cannot validate custom marks without a config file that declares them.

**Fix:** Created `wp1-sensor-sim/pytest.ini` with:
```ini
markers =
    integration: marks tests that require a running MQTT broker
```

**Rule going forward:** Every WP that uses a custom pytest mark must declare it in `pytest.ini`. Create `pytest.ini` at WP root during Phase 2 setup, before writing the first test that uses a custom mark.

---

### KI-004 -- StarletteDeprecationWarning from FastAPI TestClient

**Status:** Suppressed (2026-06-03, WP1 debug)

**Symptom:** `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` on every test run that imports `TestClient`.

**Root cause:** FastAPI >= 0.136 bundles Starlette >= 0.46, which emits this warning when the `httpx` (v1) transport is detected in TestClient. Our test code (`from fastapi.testclient import TestClient`) is correct -- the warning is internal to Starlette/FastAPI and not caused by our code.

**Fix:** Added to `pytest.ini`:
```ini
filterwarnings =
    ignore::starlette.exceptions.StarletteDeprecationWarning
```

**Rule going forward:** Library-level deprecation warnings that are not caused by our code must be suppressed with `filterwarnings` in `pytest.ini`, with a comment explaining why. Do not silently ignore warnings caused by our own code -- those must be fixed.

---

### KI-005 -- Mosquitto installed as Windows Service (no Docker)

**Status:** Documented (2026-06-03)

**Symptom:** `docker-compose up mosquitto` fails because Docker Desktop is not installed. `mosquitto.exe` runs as a System-level Windows Service (Session 0) that cannot be killed without admin rights.

**Workaround:** Install Mosquitto natively via `winget install EclipseFoundation.Mosquitto`. It runs as a Windows Service on port 1883 automatically, including on reboot. No manual start needed. Use `mosquitto-local.conf` (in `mosquitto/`) for a minimal config without Docker volume paths.

**Rule going forward:** All WP READMEs must include a "Starting Mosquitto" section with both Docker and Windows-native instructions. Do not assume Docker is available on the dev machine.

---

### KI-006 -- Non-ASCII characters in Python source files

**Status:** Resolved (2026-06-03, WP1 debug)

**Symptom:** Python source files (`control_api.py`, `main.py`, `models.py`, `simulator.py`) contained non-ASCII characters: em-dash (U+2014 `--`), arrow (U+2192 `->`), degree sign (U+00B0 `deg`). Detected by `Select-String -Pattern '[^\x00-\x7F]'`.

**Root cause:** AI agents (and editors) commonly use typographic characters (em-dashes, Unicode arrows) in docstrings and comments. While Python 3 accepts UTF-8 source files, non-ASCII in source code causes subtle issues: some terminals, grep tools, and CI log parsers mishandle them; log lines containing `->` vs `->`are harder to grep; and it is inconsistent with the project standard.

**Fix:** Replaced all non-ASCII in `.py` docstrings and comments:
- `--` (em-dash) -> `--`
- `->` (Unicode arrow) -> `->`
- `+-X degC` -> `+/-X degC`
- Degree sign in comments -> `deg`

**Rule going forward:** Python source files must be ASCII-only (docstrings, comments, string literals, log messages). Markdown documentation files may use UTF-8 (Unicode arrows in architecture diagrams, emoji in status tables are acceptable). Run the ASCII check from Section 12 best practices table before every commit. Agents must not introduce typographic characters.

---

### KI-007 -- Timestamp format: `.isoformat()` emits `+00:00`, not `Z`

**Status:** Resolved (2026-06-04, WP4 Phase 4)

**Symptom:** WP4 API responses had timestamps like `"2026-06-03T06:00:00+00:00"` instead of `"2026-06-03T06:00:00Z"`. Both are valid ISO 8601 UTC, but the project standard (P-08) requires `Z` suffix.

**Root cause:** Python's `datetime.isoformat()` for UTC-aware datetimes produces `+00:00` not `Z`. This is a Python stdlib behaviour -- not a bug, but not our convention.

**Fix:** Added `_fmt_dt(dt)` helper in `models.py`:
```python
def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
```
All `to_dict()` methods and inline datetime formatting now use `_fmt_dt()` instead of `.isoformat()`.

**Rule going forward:** Never call `.isoformat()` on a datetime in a JSON response. Always use the `_fmt_dt()` helper or equivalent `strftime(...) + "Z"` pattern. Applies to all WPs.

---

### KI-008 -- Box-drawing characters in FastAPI file headers

**Status:** Resolved (2026-06-04, WP4 Phase 4)

**Symptom:** WP4 `api.py` and `data_store.py` used `-- Section ---` style section dividers with Unicode box-drawing character U+2500 (`-`). These cause non-ASCII violations (P-12).

**Root cause:** AI-generated code pattern for visual section separation in long files.

**Fix:** Replace with ASCII `---` section comments: `# --- Section name ---`.

**Rule going forward:** Use ASCII dashes only for section dividers in Python source.

---

## 15. Three-Level Consistency Check

**The pattern:** This is an application of "Architectural Fitness Functions" (Neal Ford et al., *Building Evolutionary Architectures*). The idea: define the properties the architecture must maintain, then check them at different scopes and cadences. Not everything is checked every time -- checks are tiered by cost and by when a violation would be catchable.

---

### Level 1 -- Commit gate (every commit, ~5s)

Automated. Already enforced by Section 12 end-of-cycle workflow.

| Check | How |
|---|---|
| All tests pass | `pytest tests/ -v` -- must exit 0 |
| Zero warnings | pytest output must show `0 warnings` |
| Python source ASCII-only | `Get-Content src\*.py \| Select-String '[^\x00-\x7F]'` -- must return nothing |
| No secrets staged | `git status` -- no `.env` files |

**When it fails:** block the commit. Apply Section 13 RCA procedure.

---

### Level 2 -- Contract boundary (every time a WP touches a contract it produces or consumes)

Run when: implementing or changing a producer or consumer of any C1-C12 contract.

| Check | How |
|---|---|
| Producer output valid | Run the relevant `contracts/validators/validate_c{n}_*.py` against a sample output |
| Field names match contract | Compare Pydantic model fields against `contracts/interface-contracts.md` -- no aliases, no extras |
| Enum values match contract | Confirm sensor_type, status, quality etc. exactly match the contract enum |
| Timestamps include ms | Confirm ISO 8601 UTC with millisecond precision in all timestamp fields |

**When it fails:** do not proceed to Phase 4. Fix the divergence first, update the contract if the contract was wrong (see Section 7).

For WP1 producers: `python contracts/validators/run_phase4_check.py <captured_file>`
For WP4 producers: run `scripts/run_validators.sh` (or equivalent)

---

### Level 3 -- Harmony check (at Phase 1 kickoff and Phase 3 DoD, not every commit)

Read `checks/project-patterns.md` and tick off the 12-item checklist against the new WP. Takes ~10 minutes. This is the "does the new WP look and feel like the settled WPs?" check.

**When to run:**
- **Phase 1 kickoff** -- before writing any code. Catch structural decisions before they're baked in.
- **Phase 3 DoD** -- as part of the Definition of Done review, before declaring Phase 3 complete.

**What it checks (summary -- full details in `checks/project-patterns.md`):**

| # | Property | Why it matters |
|---|---|---|
| P-01 | Module structure matches template | Prevents WPs from drifting to incompatible layouts |
| P-02 | main.py is wiring only | Keeps entry points simple; business logic testable in isolation |
| P-03 | All config from env vars | Portability -- same code runs in Docker, native, CI |
| P-04 | Structured logging with extra={} | Log grep-ability across all services |
| P-05 | Named custom exceptions, correct HTTP codes | Predictable error handling for consumers |
| P-06 | /health returns 200 flat JSON | docker-compose healthcheck and WP7 cockpit depend on this |
| P-07 | Pydantic v2 @field_validator | Consistency; v1 pattern causes silent failures on upgrade |
| P-08 | Timestamps ISO 8601 UTC with ms | Validators and WP5 Bronze ingestion all parse this format |
| P-09 | Flat JSON responses, no envelope | WP7 and WP5 consume these directly -- wrappers break parsing |
| P-10 | snake_case fields, lowercase enums | Contract-mandated; camelCase will fail validators |
| P-11 | pytest.ini present, 0 warnings | Clean test baseline before merge |
| P-12 | Python source ASCII-only | grep-ability, portability, tool compatibility |

**Reference WPs (settled as of 2026-06-03):**
- `wp1-sensor-sim/src/` -- MQTT publisher + control API pattern
- `wp4-sap-mock/src/` -- FastAPI mock service pattern

**When it fails:** note the divergence in the session handover. Either fix it before Phase 3 closes, or raise an ADR if there is a good reason to diverge from the pattern.

---

### When each level runs

| Level | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| L1 Commit gate | on every commit | on every commit | on every commit | on every commit |
| L2 Contract boundary | -- | when implementing a producer/consumer | final check before gate | if contract changed |
| L3 Harmony check | YES -- before coding | -- | YES -- part of DoD | -- |

**The key rule:** L3 at Phase 1 costs 10 minutes and prevents structural divergence. L3 skipped at Phase 1 costs hours of refactoring at Phase 4 when the seam check finds the mismatch.
