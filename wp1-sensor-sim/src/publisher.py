"""MQTT publisher for WP1 sensor readings (Contract C1)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from .exceptions import MQTTConnectionError
from .models import SensorReading, SensorType, SENSOR_UNIT

log = logging.getLogger(__name__)

TOPIC_TEMPLATE = "factory/{plant}/{oven_id}/{sensor_type}"


class SensorPublisher:
    """Wraps a paho MQTT client and publishes C1-compliant SensorReading payloads."""

    def __init__(self, broker_host: str, broker_port: int, plant: str, oven_id: str) -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._plant = plant
        self._oven_id = oven_id
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._connected = False

    def connect(self) -> None:
        """Establish connection to the MQTT broker."""
        try:
            self._client.connect(self._broker_host, self._broker_port, keepalive=60)
            self._client.loop_start()
            log.info(
                "Connecting to MQTT broker",
                extra={"host": self._broker_host, "port": self._broker_port},
            )
        except OSError as exc:
            raise MQTTConnectionError(
                f"Cannot reach MQTT broker at {self._broker_host}:{self._broker_port}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Gracefully disconnect from the broker."""
        self._client.loop_stop()
        self._client.disconnect()
        log.info("Disconnected from MQTT broker")

    def publish_readings(
        self,
        values: dict[SensorType, float],
        order_id: Optional[str],
    ) -> None:
        """Publish one reading per sensor type to their respective C1 topics."""
        now_opc = _utc_now()
        for sensor_type, value in values.items():
            now_mqtt = _utc_now()
            reading = SensorReading(
                reading_id=str(uuid.uuid4()),
                timestamp_opc=now_opc,
                timestamp_mqtt=now_mqtt,
                plant=self._plant,
                oven_id=self._oven_id,
                sensor_type=sensor_type.value,
                value=value,
                unit=SENSOR_UNIT[sensor_type],
                quality="Good",
                order_id=order_id,
            )
            topic = TOPIC_TEMPLATE.format(
                plant=self._plant,
                oven_id=self._oven_id,
                sensor_type=sensor_type.value,
            )
            payload = json.dumps(reading.to_dict())
            result = self._client.publish(topic, payload, qos=1)
            log.debug(
                "Published reading",
                extra={
                    "topic": topic,
                    "sensor_type": sensor_type.value,
                    "value": reading.value,
                    "order_id": order_id,
                    "rc": result.rc,
                },
            )

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        self._connected = True
        log.info(
            "MQTT broker connected",
            extra={"host": self._broker_host, "port": self._broker_port, "rc": str(reason_code)},
        )

    def _on_disconnect(self, client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        self._connected = False
        log.warning("MQTT broker disconnected", extra={"rc": str(reason_code)})


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
