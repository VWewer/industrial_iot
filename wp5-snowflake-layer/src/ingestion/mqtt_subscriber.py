from __future__ import annotations

import json
import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from ..exceptions import MQTTConnectionError
from ..models import SensorReading
from ..snowflake_client import _svc

log = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO bronze_sensor_readings (
    mqtt_topic, raw_payload, reading_id, timestamp_opc, timestamp_mqtt,
    plant_id, oven_id, sensor_type, value, unit, quality, order_id
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


class MQTTSubscriber:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        topic: str = "factory/#",
    ) -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._topic = topic
        self._client = mqtt.Client()

    def connect(self) -> None:
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        try:
            self._client.connect(self._broker_host, self._broker_port)
            self._client.loop_start()
            log.info(
                "MQTT subscriber started",
                extra={
                    "host": self._broker_host,
                    "port": self._broker_port,
                    "topic": self._topic,
                },
            )
        except Exception as exc:
            raise MQTTConnectionError(
                f"Failed to connect to MQTT broker at {self._broker_host}:{self._broker_port}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        log.info("MQTT subscriber disconnected")

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            client.subscribe(self._topic, qos=1)
            log.info(
                "MQTT connected and subscribed",
                extra={"topic": self._topic, "rc": rc},
            )
        else:
            log.warning("MQTT connection returned non-zero rc", extra={"rc": rc})

    def _on_disconnect(self, client, userdata, rc) -> None:
        log.warning("MQTT broker disconnected", extra={"rc": str(rc)})

    def _on_message(self, client, userdata, msg) -> None:
        topic = msg.topic
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            reading = SensorReading(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            log.error("Malformed MQTT payload: %s", exc, extra={"topic": topic})
            return
        self._insert(topic, raw, reading)

    def _insert(self, topic: str, raw: str, reading: SensorReading) -> None:
        try:
            _svc().execute_many(
                _INSERT_SQL,
                [
                    (
                        topic,
                        raw,
                        reading.reading_id,
                        reading.timestamp_opc,
                        reading.timestamp_mqtt,
                        reading.plant,
                        reading.oven_id,
                        reading.sensor_type,
                        reading.value,
                        reading.unit,
                        reading.quality,
                        reading.order_id,
                    )
                ],
            )
            log.debug(
                "Sensor reading inserted",
                extra={
                    "reading_id": reading.reading_id,
                    "sensor_type": reading.sensor_type,
                    "order_id": reading.order_id,
                },
            )
        except Exception as exc:
            log.error(
                "Failed to insert sensor reading: %s",
                exc,
                extra={"reading_id": reading.reading_id},
            )
