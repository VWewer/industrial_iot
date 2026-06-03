#!/usr/bin/env bash
# scripts/run_validators.sh
# Runs all contract validators in contracts/validators/ against live service output.
# Each validator fetches a real sample from the relevant endpoint and validates schema.
#
# Usage:
#   ./scripts/run_validators.sh              # run all validators
#   ./scripts/run_validators.sh c1           # run only C1 validator
#   ./scripts/run_validators.sh c1 c10       # run specific validators
#
# Prerequisites:
#   - Services must be running (run ./scripts/healthcheck.sh first)
#   - Python 3.11+ with jsonschema installed (pip install jsonschema)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VALIDATORS_DIR="$REPO_ROOT/contracts/validators"

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

PASS=0
FAIL=0
SKIP=0

run_validator() {
  local name="$1"
  local script="$2"

  if [[ ! -f "$VALIDATORS_DIR/$script" ]]; then
    echo -e "  ${YELLOW}−${RESET}  ${name} — script not found (${script}), skipping"
    SKIP=$((SKIP + 1))
    return
  fi

  echo -e "  Running ${name}..."
  if python3 "$VALIDATORS_DIR/$script" 2>&1 | sed 's/^/    /'; then
    echo -e "  ${GREEN}✓${RESET}  ${name} — PASSED"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}✗${RESET}  ${name} — FAILED"
    FAIL=$((FAIL + 1))
  fi
  echo ""
}

# Parse optional filter args
FILTER_ARGS=("$@")

should_run() {
  local key="$1"
  if [[ ${#FILTER_ARGS[@]} -eq 0 ]]; then
    return 0  # run all
  fi
  for arg in "${FILTER_ARGS[@]}"; do
    if [[ "${arg,,}" == "${key,,}" ]]; then
      return 0
    fi
  done
  return 1
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Industrial IoT Demo — Contract Validators"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run a quick health check first
if ! "$SCRIPT_DIR/healthcheck.sh" --quiet; then
  echo -e "${RED}Warning: one or more services are down. Validators may fail.${RESET}"
  echo ""
fi

if should_run "c1"; then
  run_validator "C1 — MQTT sensor payload (WP1)" "validate_c1_mqtt.py"
fi

if should_run "c10"; then
  run_validator "C10 — MES cycle event (WP3 → WP5)" "validate_c10_cycle_event.py"
fi

if should_run "c12"; then
  run_validator "C12 — Gold cycle summary (WP5 → Snowflake)" "validate_c12_gold_cycle.py"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  Result: ${GREEN}${PASS} passed${RESET}  |  ${RED}${FAIL} failed${RESET}  |  ${YELLOW}${SKIP} skipped${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
