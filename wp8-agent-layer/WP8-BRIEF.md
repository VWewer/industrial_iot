# WP8 — Runtime Agent Layer (Stretch Goal)

## Status: STRETCH GOAL — not started

## Role in the architecture
WP8 adds AI agents that run inside the live system — not as build tools, but as runtime components. Two agents are scoped:

1. **Anomaly detection agent** — monitors the live sensor stream (via WP2) and raises an alert when sensor behaviour deviates from expected drying profile (e.g. moisture not decaying, temperature spike, vacuum loss)

2. **Cycle-end prediction agent** — analyses the current moisture decay curve and predicts when the target threshold will be reached, giving the operator an estimated time-to-completion

Both agents are read-only — they observe and inform, they do not actuate.

## Likely approach
- Each agent is a Python process polling WP2 REST API and/or WP5 Gold layer
- Uses Claude API (claude-sonnet-4) with structured prompts over windowed sensor data
- Outputs are exposed as a REST endpoint that WP7 can display in HMI 1 panel

## Open items — resolve before WP8 kickoff
- [ ] Confirm: LLM-based agents vs traditional statistical detection (EWMA, threshold rules)
- [ ] Define alert schema and how WP7 displays agent outputs
- [ ] Define cycle-end prediction output format (ETA timestamp + confidence)

## Session handover notes
> *To be filled at kickoff.*
