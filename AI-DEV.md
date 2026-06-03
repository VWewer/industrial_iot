# AI-DEV.md — AI-Assisted Development Methodology

> **Status:** v1.0 — June 2026  
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

**Every agent session ends with this sequence. No exceptions.**

### Agent responsibilities at session close

1. Update `WP-BRIEF.md` → `Session handover notes` with:
   - Date and session number
   - What was completed this session (specific files, functions, tests)
   - What is in progress (partially complete, needs continuation)
   - Blockers (unresolved questions, missing context, contract gaps)
   - Exact next action for the next session (first thing to do, not a summary)

2. Run `pytest tests/` and confirm pass/fail status. If failing, note which tests and why.

3. Confirm no secrets or `.env` files are staged for commit.

4. Confirm all new files follow the folder structure in the WP brief.

### Human responsibilities at session close

1. Review the session handover notes before closing.
2. Commit all changes: `git add . && git commit -m "WP{n}: {description of session output}"`
3. If a contract was changed, confirm it was updated in `contracts/interface-contracts.md` AND in all affected WP briefs.

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
Update WP-BRIEF.md → Session handover notes with:
1. Everything completed this session (file names, function names, test count)
2. What is in progress
3. Any blockers or open questions
4. The exact first action for the next session

Then run pytest tests/ and report pass/fail.
```
