"""MQTT subscriber: receives C1 sensor readings and feeds the historian."""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from .exceptions import InvalidMessageError, MQTTConnectionError
from .historian import Historian
from .models import SensorReading

log = logging.getLogger(__name__)

_REQUIRED_FIELDS = {
    "reading_id", "timestamp_opc", "timestamp_mqtt", "plant",
    "oven_id", "sensor_type", "value", "unit", "quality",
}


def _parse(payload: bytes) -> SensorReading:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidMessageError(f"JSON decode failed: {exc}") from exc

    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        raise InvalidMessageError(f"Missing fields: {missing}")

    return SensorReading(
        reading_id=data["reading_id"],
        timestamp_opc=data["timestamp_opc"],
        timestamp_mqtt=data["timestamp_mqtt"],
        plant=data["plant"],
        oven_id=data["oven_id"],
        sensor_type=data["sensor_type"],
        value=float(data["value"]),
        unit=data["unit"],
        quality=data["quality"],
        order_id=data.get("order_id"),
    )


class SensorSubscriber:
    """Paho-MQTT subscriber for the factory/# topic hierarchy."""

    def __init__(
        self,
        historian: Historian,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        on_reading: Optional[Callable[[SensorReading], None]] = None,
    ) -> None:
        self._historian = historian
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._on_reading = on_reading
        self._client: mqtt.Client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="wp2-simatic-mock",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    # --- lifecycle ---

    def connect(self) -> None:
        """Connect synchronously and start the network loop in a background thread."""
        try:
            self._client.connect(self._broker_host, self._broker_port, keepalive=60)
        except OSError as exc:
            raise MQTTConnectionError(
                f"Cannot reach MQTT broker at {self._broker_host}:{self._broker_port}"
            ) from exc
        self._client.loop_start()
        log.info(
            "MQTT subscriber connecting",
            extra={"host": self._broker_host, "port": self._broker_port},
        )

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        log.info("MQTT subscriber disconnected")

    # --- callbacks ---

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.error(
                "MQTT connection refused",
                extra={"reason": str(reason_code)},
            )
            return
        client.subscribe("factory/#", qos=1)
        log.info("MQTT subscriber connected and subscribed to factory/#")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        log.warning("MQTT broker disconnected", extra={"rc": str(reason_code)})

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            reading = _parse(msg.payload)
        except InvalidMessageError as exc:
            log.warning(
                "Dropping invalid MQTT message",
                extra={"topic": msg.topic, "error": str(exc)},
            )
            return

        self._historian.add(reading)
        log.debug(
            "Reading stored",
            extra={
                "oven_id": reading.oven_id,
                "sensor_type": reading.sensor_type,
                "value": reading.value,
            },
        )
        if self._on_reading:
            self._on_reading(reading)
