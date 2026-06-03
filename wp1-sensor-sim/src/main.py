"""Entry point for WP1 — starts the MQTT publisher and control API together."""
from __future__ import annotations

import logging
import os
import threading

import uvicorn
from dotenv import load_dotenv

from .control_api import app, init_app
from .exceptions import MQTTConnectionError
from .models import CycleState, SensorType
from .publisher import SensorPublisher
from .simulator import CycleSimulator

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


def _build_simulator(publisher: SensorPublisher, compression: float, interval_s: float) -> CycleSimulator:
    def on_tick(state: CycleState, values: dict[SensorType, float]) -> None:
        order_id = simulator.active_order_id
        publisher.publish_readings(values, order_id)

    simulator = CycleSimulator(
        compression_factor=compression,
        publish_interval_s=interval_s,
        on_tick=on_tick,
    )
    return simulator


def main() -> None:
    broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
    broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    publish_interval_s = float(os.getenv("SENSOR_PUBLISH_INTERVAL_S", "5"))
    plant = os.getenv("PLANT_ID", "regensburg")
    oven_id = os.getenv("OVEN_ID", "oven-01")
    compression = float(os.getenv("CYCLE_TIME_COMPRESSION", "60.0"))
    api_port = int(os.getenv("CONTROL_API_PORT", "8000"))

    log.info(
        "WP1 starting",
        extra={
            "broker": f"{broker_host}:{broker_port}",
            "plant": plant,
            "oven_id": oven_id,
            "compression": compression,
        },
    )

    publisher = SensorPublisher(
        broker_host=broker_host,
        broker_port=broker_port,
        plant=plant,
        oven_id=oven_id,
    )

    try:
        publisher.connect()
    except MQTTConnectionError as exc:
        log.error("Failed to connect to MQTT broker: %s", exc)
        raise SystemExit(1) from exc

    simulator = _build_simulator(publisher, compression, publish_interval_s)
    init_app(simulator)

    # Run the API in a daemon thread so it doesn't block the main process
    api_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "0.0.0.0", "port": api_port, "log_level": "warning"},
        daemon=True,
        name="control-api",
    )
    api_thread.start()
    log.info("Control API listening on port %d", api_port)

    # Keep main thread alive
    api_thread.join()

    publisher.disconnect()


if __name__ == "__main__":
    main()
