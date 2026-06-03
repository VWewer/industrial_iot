# contracts/seed-data — Reference Data

This folder contains the canonical seed data for the Industrial IoT Demo project. All development, testing, and demo runs use this data. Never invent data inline in tests or WP code — load from these files.

## Files

| File | Records | Purpose |
|---|---|---|
| `material_masters.json` | 4 | MaterialMaster objects — 4 transformer types with full spec |
| `production_orders.json` | 3 | ProductionOrder objects — 1 RELEASED (demo), 1 CONFIRMED, 1 ABORTED |
| `historical_cycles.json` | 20 | gold_cycle_summary records — 90 days of history across all 4 materials |

## Schema

All field names match `DOMAIN-MODEL.md` exactly. Do not alias or abbreviate.

## How to use in tests

```python
# tests/conftest.py
import json
import pytest
from pathlib import Path

SEED_DATA = Path(__file__).parent.parent.parent / "contracts" / "seed-data"

@pytest.fixture
def material_masters():
    return json.loads((SEED_DATA / "material_masters.json").read_text())

@pytest.fixture
def production_orders():
    return json.loads((SEED_DATA / "production_orders.json").read_text())

@pytest.fixture
def historical_cycles():
    return json.loads((SEED_DATA / "historical_cycles.json").read_text())
```

## Demo state at startup

The seed data assumes this state for a fresh demo run:

- `ORD-2026-00042` — status: `RELEASED` — this is the active demo order (WF1 → WF4)
- `ORD-2026-00041` — status: `CONFIRMED` — most recent historical cycle
- `ORD-2026-00039` — status: `ABORTED` — demonstrates deviation case
- 20 historical cycles in `historical_cycles.json` — pre-populate Gold layer on startup

## Adding seed data

If a test case requires data not covered here, add to the relevant file and note it in your session handover. Do not add more than 5 records at a time without discussing first — seed data is kept minimal and purposeful.

## Distribution of historical cycles

| material_id | cycles | spec_met | notable cases |
|---|---|---|---|
| MAT-0001 (100MVA) | 7 | 6/7 | ORD-2026-00017: significant overrun + spec fail |
| MAT-0002 (1MVA) | 6 | 6/6 | All on spec — reliable short cycle |
| MAT-0003 (CT 36kV) | 4 | 3/4 | ORD-2026-00029: marginal spec fail |
| MAT-0004 (400MVA) | 3 | 2/3 | ORD-2026-00005: major overrun (450 min delta) |

This distribution makes the analytics panel interesting: MAT-0004 consistently runs long, MAT-0002 is the most reliable, MAT-0001 has one notable outlier.
