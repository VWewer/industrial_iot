# Contributing — Code Standards

This document defines the code quality standards for the Industrial IoT Demo project. Every agent and developer working on a workpackage reads this before writing code. Standards are enforced at the Definition of Done stage in each WP brief.

---

## Language and runtime

| Layer | Language | Runtime |
|---|---|---|
| Simulators, pipelines, agents | Python 3.11+ | — |
| Mock services (REST APIs) | Python + FastAPI | uvicorn |
| Analytical dashboard | Python + Streamlit | — |
| Unified cockpit | Python + Streamlit (multi-page) or React | — |
| Schema / config | JSON, YAML, SQL | — |

Do not introduce new languages or frameworks without an ADR in `docs/decisions.md`.

---

## Project structure per workpackage

Each WP folder follows this layout:

```
wp{n}-{name}/
  WP-BRIEF.md         Scope, contracts, DoD — the agent prompt document
  README.md           How to run this WP in isolation
  src/                All source code
    main.py           Entry point (or main.py equivalent)
    {module}.py       One module per logical concern
  tests/
    test_{module}.py  Unit tests mirroring src/ structure
  requirements.txt    WP-specific dependencies
  .env.example        Required environment variables (no secrets)
```

---

## Python standards

### Typing
- All functions must have type annotations on parameters and return values.
- Use `from __future__ import annotations` at the top of every file.
- Use `TypedDict` or `dataclasses` for structured payloads — never raw `dict` with no shape.

```python
# correct
def publish_reading(reading: SensorReading, topic: str) -> bool:
    ...

# wrong
def publish_reading(reading, topic):
    ...
```

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- No abbreviations unless they are domain-standard (`mqtt`, `opc`, `plc`, `sku`)

### Module size
- Maximum ~200 lines per module. If a module is growing beyond that, split it.
- One logical concern per module. A module that both publishes MQTT and manages historian state should be two modules.

### Error handling
- Never use bare `except:` or `except Exception:` without logging.
- All I/O operations (network, file, DB) must be wrapped in try/except with a logged error and a defined fallback or raised custom exception.
- Define custom exception classes in a `exceptions.py` per WP when the WP has more than two distinct failure modes.

### Logging
- Use Python `logging` module, not `print()`.
- Log at appropriate levels: `DEBUG` for per-reading noise, `INFO` for state transitions, `WARNING` for degraded operation, `ERROR` for failures.
- Include structured context in log messages: `log.info("Cycle started", extra={"order_id": order_id, "oven_id": oven_id})`

### Configuration
- All configuration comes from environment variables loaded via `python-dotenv`.
- No hardcoded hostnames, ports, credentials, or topic names in source code.
- Every WP has a `.env.example` listing all required variables with descriptions.

### Dependencies
- Pin all dependencies in `requirements.txt` with exact versions (`==`), not ranges.
- Do not add a dependency for something achievable in 10 lines of stdlib.

---

## Interface discipline

The `/contracts` folder is the source of truth for all inter-WP interfaces. Before implementing any producer or consumer:

1. Read the relevant contract in `contracts/interface-contracts.md`.
2. Implement exactly to the contract — do not extend or modify the schema unilaterally.
3. If a contract needs to change, update `contracts/interface-contracts.md` first and note the reason. All WPs affected by the change must be flagged.

**Schema changes after WP5 has ingested data require a migration note in `contracts/interface-contracts.md`.**

---

## Testing standards

- Every public function in `src/` has at least one unit test.
- Tests use `pytest`. No other test framework.
- Tests must be runnable with `pytest tests/` from the WP root without any external services running (mock or stub external calls).
- Minimum coverage target: 70% per WP. Coverage report generated with `pytest --cov=src`.
- Integration tests (requiring live services) go in `tests/integration/` and are excluded from the default run.

---

## Documentation standards

- Every module has a module-level docstring explaining its role in one or two sentences.
- Every non-trivial function has a docstring. "Non-trivial" means anything with a side effect, I/O, or business logic.
- The WP `README.md` must include: purpose, how to run locally, required env vars, and a note on what the WP produces for downstream consumers.

---

## Git discipline

- Branch naming: `wp{n}/{short-description}` (e.g. `wp1/sensor-sim-base`, `wp5/bronze-ingestion`)
- Commit messages: imperative mood, max 72 chars subject line (`Add MQTT publisher for temperature node`)
- One logical change per commit. Do not bundle unrelated changes.
- No commented-out code in commits. Use git history for recovery.
- No secrets, credentials, or `.env` files committed. `.env` is in `.gitignore`.
