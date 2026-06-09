"""Entry point for WP2 -- wires historian, subscriber, and API then starts both."""
from __future__ import annotations

import logging
import os
import threading

import uvicorn
from dotenv import load_dotenv

from .api import app, init_app
from .exceptions import MQTTConnectionError
from .historian import Historian
from .subscriber import SensorSubscriber

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
    broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    api_port = int(os.getenv("SIMATIC_API_PORT", "8001"))
    max_readings = int(os.getenv("HISTORIAN_MAX_READINGS_PER_CHANNEL", "500"))
    moisture_threshold = float(os.getenv("MOISTURE_THRESHOLD_PPM", "500"))
    max_cycle_minutes = float(os.getenv("MAX_CYCLE_MINUTES", "600"))

    log.info(
        "WP2 starting",
        extra={
            "broker": f"{broker_host}:{broker_port}",
            "api_port": api_port,
            "max_readings": max_readings,
        },
    )

    historian = Historian(max_readings=max_readings)
    subscriber = SensorSubscriber(
        historian=historian,
        broker_host=broker_host,
        broker_port=broker_port,
    )

    try:
        subscriber.connect()
    except MQTTConnectionError as exc:
        log.error("Failed to connect to MQTT broker: %s", exc)
        raise SystemExit(1) from exc

    init_app(historian, moisture_threshold, max_cycle_minutes)

    api_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "0.0.0.0", "port": api_port, "log_level": "warning"},
        daemon=True,
        name="simatic-api",
    )
    api_thread.start()
    log.info("SIMATIC API listening on port %d", api_port)

    api_thread.join()

    subscriber.disconnect()


if __name__ == "__main__":
    main()
