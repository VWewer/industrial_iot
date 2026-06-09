"""
Phase 4 seam check runner for WP1.
Reads mosquitto_sub captured output (topic<space>payload lines),
validates each payload against C1, and prints a summary.

Usage:
    python run_phase4_check.py <captured_file>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_c1_mqtt import validate


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_phase4_check.py <captured_file>")
        sys.exit(1)

    captured = Path(sys.argv[1])
    lines = [l.strip() for l in captured.read_text(encoding="utf-8").splitlines() if l.strip()]

    passed = 0
    failed = 0

    for line in lines:
        parts = line.split(" ", 1)
        if len(parts) != 2:
            print(f"SKIP (unexpected format): {line[:80]}")
            continue
        topic, payload_str = parts
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            print(f"SKIP (bad JSON on {topic}): {exc}")
            failed += 1
            continue

        errors = validate(payload)
        sensor = payload.get("sensor_type", "?")
        if not errors:
            print(f"  PASS  {topic}  [{sensor}]  value={payload.get('value')} {payload.get('unit')}")
            passed += 1
        else:
            print(f"  FAIL  {topic}  [{sensor}]")
            for e in errors:
                print(f"         • {e}")
            failed += 1

    print()
    print(f"Result: {passed} passed, {failed} failed out of {passed + failed} payloads")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
