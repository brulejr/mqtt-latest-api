import json
import logging
import socket
from typing import Any

import paho.mqtt.client as mqtt

from app.config import AppConfig
from app.store import LatestMessageStore

logger = logging.getLogger(__name__)


def get_path_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        if part not in current:
            return None

        current = current[part]

    return current


def message_matches_filter(
    payload: dict[str, Any],
    filter_path: str | None,
    filter_value: str | None,
) -> bool:
    if not filter_path:
        return True

    actual_value = get_path_value(payload, filter_path)

    if actual_value is None:
        return False

    if filter_value is None or filter_value == "":
        return True

    return str(actual_value) == filter_value


class MqttIngestClient:
    def __init__(
        self,
        config: AppConfig,
        store: LatestMessageStore,
    ):
        self._config = config
        self._store = store

        client_id = f"mqtt-latest-api-{socket.gethostname()}"

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )

        if config.mqtt_username:
            self._client.username_pw_set(
                username=config.mqtt_username,
                password=config.mqtt_password,
            )

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def start(self) -> None:
        logger.info(
            "Connecting to MQTT broker host=%s port=%s topics=%s",
            self._config.mqtt_host,
            self._config.mqtt_port,
            self._config.mqtt_topics,
        )

        self._client.connect_async(
            self._config.mqtt_host,
            self._config.mqtt_port,
            keepalive=60,
        )

        self._client.loop_start()

    def stop(self) -> None:
        logger.info("Stopping MQTT client")
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            logger.error("MQTT connection failed: %s", reason_code)
            return

        logger.info("Connected to MQTT broker: %s", reason_code)

        for topic in self._config.mqtt_topics:
            logger.info("Subscribing to MQTT topic: %s", topic)
            client.subscribe(topic)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        logger.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        topic = message.topic

        try:
            decoded = message.payload.decode("utf-8")
            payload = json.loads(decoded)

            if not isinstance(payload, dict):
                logger.warning("Ignoring non-object JSON message topic=%s", topic)
                return

            if not message_matches_filter(
                payload=payload,
                filter_path=self._config.mqtt_filter_path,
                filter_value=self._config.mqtt_filter_value,
            ):
                logger.debug("Ignoring message that does not match filter topic=%s", topic)
                return

            discriminator = get_path_value(
                payload,
                self._config.mqtt_discriminator_path,
            )

            if discriminator is None:
                logger.warning(
                    "Ignoring message missing discriminator path=%s topic=%s",
                    self._config.mqtt_discriminator_path,
                    topic,
                )
                return

            key = str(discriminator)

            item = self._store.upsert(
                key=key,
                topic=topic,
                payload=payload,
            )

            logger.debug(
                "Stored latest MQTT message key=%s topic=%s received_at=%s",
                item["key"],
                item["topic"],
                item["received_at"],
            )

        except json.JSONDecodeError:
            logger.warning("Ignoring non-JSON MQTT message topic=%s", topic)

        except Exception:
            logger.exception("Unexpected error while processing MQTT message topic=%s", topic)
