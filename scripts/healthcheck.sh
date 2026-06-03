#!/usr/bin/env bash
# scripts/healthcheck.sh
# Hits every WP /health endpoint and the MQTT broker.
# Reports UP / DOWN for each service and exits non-zero if any are down.
#
# Usage:
#   ./scripts/healthcheck.sh
#   ./scripts/healthcheck.sh --quiet    # suppress detail, only show failures

set -euo pipefail

QUIET=false
[[ "${1:-}" == "--quiet" ]] && QUIET=true

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

PASS=0
FAIL=0

check_http() {
  local name="$1"
  local url="$2"
  local response
  local http_code

  http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null || echo "000")

  if [[ "$http_code" == "200" ]]; then
    [[ "$QUIET" == false ]] && echo -e "  ${GREEN}✓${RESET}  ${name} (${url}) — UP"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}✗${RESET}  ${name} (${url}) — DOWN (HTTP ${http_code})"
    FAIL=$((FAIL + 1))
  fi
}

check_mqtt() {
  local name="$1"
  local host="$2"
  local port="$3"

  if command -v mosquitto_pub &>/dev/null; then
    if mosquitto_pub -h "$host" -p "$port" -t "healthcheck" -m "ping" -q 1 --timeout 3 2>/dev/null; then
      [[ "$QUIET" == false ]] && echo -e "  ${GREEN}✓${RESET}  ${name} (${host}:${port}) — UP"
      PASS=$((PASS + 1))
    else
      echo -e "  ${RED}✗${RESET}  ${name} (${host}:${port}) — DOWN"
      FAIL=$((FAIL + 1))
    fi
  else
    # Fallback: TCP check via /dev/tcp if mosquitto_pub not available
    if (echo >/dev/tcp/"$host"/"$port") 2>/dev/null; then
      [[ "$QUIET" == false ]] && echo -e "  ${GREEN}✓${RESET}  ${name} (${host}:${port}) — UP (TCP only)"
      PASS=$((PASS + 1))
    else
      echo -e "  ${RED}✗${RESET}  ${name} (${host}:${port}) — DOWN"
      FAIL=$((FAIL + 1))
    fi
  fi
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Industrial IoT Demo — Service Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Infrastructure:"
check_mqtt "Mosquitto (MQTT broker)" "localhost" "1883"

echo ""
echo "WP Services:"
check_http "WP1 — Sensor Simulator (Control API)" "http://localhost:8000/health"
check_http "WP2 — SIMATIC Mock"                   "http://localhost:8001/health"
check_http "WP3 — Mendix Mock"                    "http://localhost:8002/health"
check_http "WP4 — SAP Mock"                       "http://localhost:8003/health"
check_http "WP5 — Snowflake Layer (Webhook)"      "http://localhost:8005/health"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  Result: ${GREEN}${PASS} UP${RESET}  |  ${RED}${FAIL} DOWN${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
