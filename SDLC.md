# SDLC.md — Delivery Process

> **Status:** v1.1 — June 2026  
> **Changes from v1.0:** Added explicit phase gates with entry/exit criteria, milestone map, references to DOMAIN-MODEL.md and AI-DEV.md as required pre-reads.

This document defines how work progresses through the project — from brief to implementation to integrated. It applies to both human developers and AI agents working on workpackages. **Reading this before starting any WP is mandatory.**

---

## Required pre-reads before any implementation begins

Before writing a single line of code, read these four documents in full:

| Document | What it covers |
|---|---|
| `DOMAIN-MODEL.md` | Canonical object schemas, all 6 workflows, data flows, state machine, seed data |
| `CONTRIBUTING.md` | Code standards: typing, naming, error handling, logging, testing, git |
| `AI-DEV.md` | Agent session protocol, WP brief structure, prompt patterns, skill library |
| `contracts/interface-contracts.md` | All inter-WP interface contracts (field-level schemas) |

---

## Phases overview

```
Phase 0   Contracts + domain model    ← COMPLETE
    ↓
Phase 1   WP kickoff                  ← per WP
    ↓
Phase 2   Implementation              ← per WP
    ↓
Phase 3   Definition of Done          ← per WP
    ↓
Phase 4   Interface validation        ← per WP, at seams
    ↓
Phase 5   WP7 integration             ← project milestone
```

---

## Phase 0 — Contracts and domain model (do this once, before any WP starts)

**Status: COMPLETE**

Phase 0 is complete when ALL of the following are true:

- [x] `DOMAIN-MODEL.md` — canonical schemas, all workflows, state machine, seed data
- [x] `contracts/interface-contracts.md` — all inter-WP contracts reviewed and stable
- [x] `contracts/mqtt-schema.json` — MQTT topic + payload schema defined
- [x] `contracts/rest-endpoints.yaml` — all REST endpoints specified
- [x] `contracts/snowflake-schema.sql` — Bronze/Silver/Gold DDL defined
- [x] `contracts/seed-data/` — reference data defined (4 materials, 3 orders, 20 historical cycles)
- [x] `docs/decisions.md` — key ADRs recorded (DuckDB superseded by real Snowflake — see ADR-005)

**Gate: no WP writes implementation code until Phase 0 is complete.**

---

## Phase 1 — WP kickoff

### Entry criteria
- Phase 0 complete
- All upstream WP contracts stable (not necessarily implemented — contracts stable)
- WP-BRIEF.md exists and is current

### What happens
1. Read the WP brief (`WP-BRIEF.md`) in full
2. Read `CONTRIBUTING.md`, `SDLC.md`, `AI-DEV.md`, `DOMAIN-MODEL.md`
3. Read relevant contracts — identify which this WP produces or consumes
4. Read upstream WP briefs for any WP this one depends on
5. Surface ambiguities — resolve before writing code (see AI-DEV.md §4)
6. Confirm exact deliverables for this session

> **Skill prompt — Phase 1:** The agent will ask: *"Want to /grill-me on this design before we start coding?"*  
> Use `/grill-me` to stress-test scope, contracts, and edge cases before any implementation begins. Especially valuable for WP3, WP5, and WP7.

### Exit criteria (move to Phase 2)
- All ambiguities in WP-BRIEF.md Open Items are resolved
- Agent has confirmed scope and deliverables for the session
- No outstanding contract questions

---

## Phase 2 — Implementation

### Entry criteria
- Phase 1 complete for this WP

### Rules
- Work inside the WP folder only — do not modify other WP folders or contracts
- Follow `CONTRIBUTING.md` throughout — no deferred cleanup
- Commit in logical increments (see git discipline in `CONTRIBUTING.md`)
- If a contract needs to change: **stop** — see contract change protocol below

> **Skills active during Phase 2 (automatic):**  
> `python-pro` — typing, async, dataclass patterns applied throughout  
> `fastapi-expert` — routing, Pydantic v2, lifespan for all FastAPI WPs (WP1–WP4)  
> `api-designer` — consulted on any contract or endpoint question  
> `debugging-wizard` — applied automatically on any test failure before attempting a fix  
> `devops-engineer` — applied on any Dockerfile or docker-compose change  

### Contract change protocol
If implementation reveals a contract needs to change:
1. Stop implementation
2. Update `contracts/interface-contracts.md`
3. Update `DOMAIN-MODEL.md` if the affected object is defined there
4. Note the reason in `docs/decisions.md` if it's an architectural change
5. Flag all affected WPs in their briefs
6. Resume implementation

**Never silently implement a diverging schema.**

### Exit criteria (move to Phase 3)
- All `src/` modules implemented
- `requirements.txt` pinned and complete
- `.env.example` present with all variables documented
- `tests/` written (not necessarily all passing)
- No secrets in staged files

---

## Phase 3 — Definition of Done

> **Skill prompt — Phase 3:** The agent will ask: *"Run test-master review to check coverage gaps before we sign off?"*  
> `test-master` reviews the test suite for missing cases, integration gaps, and coverage blind spots. `monitoring-expert` checks structured logging discipline. Both are lightweight — 5 minutes, high value.

### Standard DoD (every WP)

- [ ] All source code in `src/` with correct structure per WP-BRIEF.md
- [ ] `requirements.txt` pinned with exact versions (`==`)
- [ ] `.env.example` present with all required variables and descriptions
- [ ] `pytest tests/` passes with no failures
- [ ] Coverage ≥ 70% (`pytest --cov=src tests/`)
- [ ] `README.md` complete: purpose, how to run, required env vars, sample output
- [ ] WP-specific DoD criteria in `WP-BRIEF.md` all checked
- [ ] No secrets, credentials, or `.env` files committed

### WP-specific DoD criteria
Defined in each `WP-BRIEF.md`. These are in addition to the standard DoD above.

### Exit criteria (move to Phase 4)
All DoD checkboxes checked. No exceptions — partial DoD is not done.

---

## Phase 4 — Interface validation (seam check)

> **Skills active during Phase 4 (automatic):**  
> `code-reviewer` — full checklist review of the WP branch before merge to main  
> `secure-code-guardian` — security review of any API endpoints or input handling  
> `sql-pro` + `database-optimizer` — applied on WP5 and WP6 query validation  
> **Skill prompt:** *"Run /review on the WP branch before merging?"*

**This is the most important phase for integration quality.** A WP that passes its own DoD but fails at the seam is not complete.

### For producers (WPs that publish data)

1. Run the WP in isolation
2. Capture a sample output (MQTT message, REST response, DB row)
3. Validate against the contract schema field by field:
   - Field names match exactly (case-sensitive)
   - Types match (string vs int vs float vs boolean)
   - Required fields present
   - Nullable fields correctly nullable
   - Enum values within defined set
   - Timestamps in ISO 8601 UTC
4. Document the validated sample in `README.md` under "Sample output"

**Validation tool:** Run `contracts/validators/{contract_id}_validator.py` with the sample output.

### For consumers (WPs that read data from another WP)

1. Write an integration test in `tests/integration/` that starts the upstream WP (or a stub of it) and verifies the consumer can read and process its output
2. The seam-check question: **"Does what WP{n} produces match exactly what I expect to consume — field names, types, units, topic structure, enum values?"**
3. If no: fix in the producer, not the consumer. Update the contract if needed.

### Exit criteria (move to Phase 5 / integration)
- Producer: sample output validated against contract, documented in README
- Consumer: integration test exists and passes

---

## Phase 5 — WP7 integration

> **Skill prompt — Phase 5 entry:** Before WP7 begins, the agent will ask:  
> *"Want to /grill-me on the integration plan?"* — stress-test the wiring design  
> *"Run secure-code-guardian review across all API surfaces?"* — one security pass before the unified cockpit exposes everything

WP7 is the integration milestone. **Before WP7 begins, all of the following must be true:**

| WP | Required state |
|---|---|
| WP1 | Phase 4 complete — MQTT stream validated |
| WP2 | Phase 4 complete — process state REST API validated |
| WP3 | Phase 4 complete — operator workflow REST API validated |
| WP4 | Phase 4 complete — SAP OData endpoints validated |
| WP5 | Phase 4 complete — Gold layer queryable with seed data |
| WP6 | Phase 4 complete — SiS dashboard running against WP5 Gold |

**WP7 does not implement business logic.** It wires existing services. If something doesn't work in WP7, the fix goes in the upstream WP.

---

## Milestone map

| Milestone | What it means | Gate |
|---|---|---|
| M0 — Contracts complete | Phase 0 done, all contracts stable | No code before this |
| M1 — Foundation running | WP1 + WP4 Phase 4 complete | WP2, WP3, WP5 can start |
| M2 — Mid-stack running | WP2 + WP3 Phase 4 complete | WP5 can fully integrate |
| M3 — Data layer complete | WP5 Phase 4 complete, Gold queryable | WP6 can deploy |
| M4 — Dashboard live | WP6 (SiS) Phase 4 complete | WP7 can begin |
| M5 — Integration complete | WP7 full demo workflow end-to-end | Portfolio ready |
| M6 — Agents (stretch) | WP8 Phase 4 complete | — |

---

## Dependency order

```
M0: Phase 0 complete (blocks everything)

Parallel: WP1, WP4          (no upstream dependencies)

WP2 needs: WP1 MQTT schema stable (M1 partial)
WP3 needs: WP2 REST spec + WP4 OData spec stable

M1: WP1 + WP4 Phase 4 complete

WP5 needs: WP1 MQTT schema + WP3/WP4 REST specs stable
           (full integration needs WP1+WP3+WP4 running)

M2: WP2 + WP3 Phase 4 complete

WP6 needs: WP5 Gold schema stable + Snowflake account configured

M3: WP5 Phase 4 complete

M4: WP6 Phase 4 complete (SiS deployed)

WP7 needs: WP2-WP6 all Phase 4 complete

M5: WP7 integration complete

WP8: Stretch — needs WP2 + WP5 running
```

"Schema stable" = contract signed off. Upstream WP does not need to be running — only the interface contract agreed.

---

## Agent session protocol

See `AI-DEV.md` for the full agent methodology. Summary:

**Session open (always):**
1. Provide: `CONTRIBUTING.md`, `SDLC.md`, `AI-DEV.md`, `DOMAIN-MODEL.md`, WP-BRIEF.md, relevant contracts
2. State the current phase explicitly
3. If continuing: provide session handover notes from WP-BRIEF.md

**Session close (always):**
1. Agent updates WP-BRIEF.md session handover notes
2. Agent runs pytest and reports pass/fail
3. Human commits all changes before closing

**Mid-session contract change:**
Stop → update contract → update DOMAIN-MODEL.md → flag affected WPs → resume.

---

## Architecture Decision Records

Significant design decisions are recorded in `docs/decisions.md`. Format:

```markdown
## ADR-{n}: {short title}
Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded

### Context
What situation forced a decision.

### Decision
What was decided.

### Consequences
What this means — trade-offs, constraints introduced.
```

Write an ADR when: a framework or library is chosen, a contract changes after Phase 0, a WP scope changes significantly, or a technical approach is chosen over a plausible alternative.
