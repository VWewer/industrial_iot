"""Generate seed_cycle.json — a deterministic pre-recorded drying cycle for replay mode.

Run once: python data/generate_seed.py
"""
from __future__ import annotations

import json
import math
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

random.seed(42)

PLANT = "regensburg"
OVEN_ID = "oven-01"
ORDER_ID = "ORD-2026-00042"

# Cycle parameters (matching MAT-0001: Power Transformer 100MVA)
TARGET_TEMP = 120.0
TARGET_VACUUM = 5.0
TARGET_MOISTURE = 300.0
STANDARD_CYCLE_MIN = 480.0
WARMING_MIN = 60.0
AMBIENT_TEMP = 25.0
ATMOSPHERIC = 1013.0
INITIAL_MOISTURE = 5000.0

PUBLISH_INTERVAL_MIN = 5.0  # one reading per sensor every 5 simulated minutes
NOISE = {"temperature": 0.5, "vacuum": 0.05, "moisture": 10.0}


def jitter(value: float, stddev: float) -> float:
    return value + random.gauss(0.0, stddev)


def temperature_at(t: float) -> float:
    if t <= WARMING_MIN:
        tau = WARMING_MIN / 3.0
        base = AMBIENT_TEMP + (TARGET_TEMP - AMBIENT_TEMP) * (1.0 - math.exp(-t / tau))
    else:
        base = TARGET_TEMP
    return round(jitter(base, NOISE["temperature"]), 3)


def vacuum_at(t: float) -> float:
    if t <= WARMING_MIN:
        return round(jitter(ATMOSPHERIC, NOISE["vacuum"]), 3)
    drying_t = t - WARMING_MIN
    tau = 10.0
    base = TARGET_VACUUM + (ATMOSPHERIC - TARGET_VACUUM) * math.exp(-drying_t / tau)
    return round(max(jitter(base, NOISE["vacuum"]), 0.1), 3)


def moisture_at(t: float) -> float:
    if t <= WARMING_MIN:
        return round(jitter(INITIAL_MOISTURE, NOISE["moisture"]), 3)
    drying_t = t - WARMING_MIN
    k = -math.log(TARGET_MOISTURE / INITIAL_MOISTURE) / STANDARD_CYCLE_MIN
    base = INITIAL_MOISTURE * math.exp(-k * drying_t)
    return round(max(jitter(base, NOISE["moisture"]), 0.0), 3)


def cycle_state_at(t: float, moisture: float) -> str:
    if t == 0:
        return "idle"
    if t <= WARMING_MIN:
        return "warming"
    if moisture <= TARGET_MOISTURE:
        return "complete"
    return "drying"


def utc_ts(base: datetime, offset_min: float) -> str:
    ts = base + timedelta(minutes=offset_min)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def main() -> None:
    readings = []
    base_time = datetime(2026, 6, 3, 6, 0, 0, tzinfo=timezone.utc)
    total_minutes = WARMING_MIN + STANDARD_CYCLE_MIN + PUBLISH_INTERVAL_MIN  # one tick past threshold

    t = 0.0
    while t <= total_minutes:
        temp = temperature_at(t)
        vac = vacuum_at(t)
        moist = moisture_at(t)
        state = cycle_state_at(t, moist)

        for sensor_type, value, unit in [
            ("temperature", temp, "degC"),
            ("vacuum", vac, "mbar"),
            ("moisture", moist, "ppm"),
        ]:
            readings.append({
                "reading_id": str(uuid.UUID(int=len(readings), version=4)),
                "timestamp_opc": utc_ts(base_time, t),
                "timestamp_mqtt": utc_ts(base_time, t),
                "plant": PLANT,
                "oven_id": OVEN_ID,
                "sensor_type": sensor_type,
                "value": value,
                "unit": unit,
                "quality": "Good",
                "order_id": ORDER_ID if t > 0 else None,
                "_meta": {"simulated_minute": t, "cycle_state": state},
            })

        if state == "complete":
            break
        t += PUBLISH_INTERVAL_MIN

    output = {
        "description": "Pre-recorded drying cycle for WP1 replay mode — MAT-0001 Power Transformer 100MVA",
        "order_id": ORDER_ID,
        "plant": PLANT,
        "oven_id": OVEN_ID,
        "cycle_parameters": {
            "target_temperature_degC": TARGET_TEMP,
            "target_vacuum_mbar": TARGET_VACUUM,
            "target_moisture_ppm": TARGET_MOISTURE,
            "standard_cycle_minutes": STANDARD_CYCLE_MIN,
            "warming_duration_minutes": WARMING_MIN,
        },
        "total_readings": len(readings),
        "readings": readings,
    }

    out_path = Path(__file__).parent / "seed_cycle.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(readings)} readings to {out_path}")


if __name__ == "__main__":
    main()
