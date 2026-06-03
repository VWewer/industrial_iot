# checks/

This directory contains the project-level consistency and quality check artifacts used by the three-level consistency system (see `AI-DEV.md` Section 15 and `CONTRIBUTING.md`).

---

## Contents

| File | Purpose | When to use |
|---|---|---|
| `project-patterns.md` | 12 golden patterns extracted from settled reference WPs (WP1 + WP4) | Level 3 harmony check at Phase 1 kickoff and Phase 3 DoD re-run |

---

## When to run checks

### Level 3 harmony check (the one in this directory)

Run at two mandatory points per WP:

1. **Phase 1 kickoff** — before writing any code. Tick off all 12 patterns in `project-patterns.md` against your planned structure.
2. **Phase 3 DoD re-run** — before signing off the WP as done. Confirm the implemented structure still matches all 12 patterns.

**How:** Open `project-patterns.md`. Work through the checklist table at the bottom. For each pattern, verify your planned or implemented WP matches. If a pattern is not applicable to your WP, mark it N/A with a note.

### Level 1 (automated)

```
pytest tests/ -v --cov=src
```

Run on every commit. Expected: 0 failures, 0 warnings, coverage >= 70%.

### Level 2 (contract boundary)

Run at Phase 4 seam check. Use the validators in `contracts/validators/`. See `SDLC.md` Phase 4 for the procedure.

---

## Adding new patterns

When a settled WP reveals a pattern not yet in `project-patterns.md`:

1. Add it as P-13, P-14, etc. following the existing format.
2. Note which WP the pattern was extracted from.
3. Update the summary checklist table at the bottom of `project-patterns.md`.
4. Commit the update with message: `docs: add pattern P-{n} from WP{x} to project-patterns.md`

Patterns should be stable, observable, and checkable without running code — the goal is reading discipline, not automated analysis.
