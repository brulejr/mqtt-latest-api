import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_topics: list[str]

    mqtt_discriminator_path: str

    mqtt_filter_path: str | None
    mqtt_filter_value: str | None

    store_max_items: int
    log_level: str

    @staticmethod
    def from_env() -> "AppConfig":
        topics = os.getenv("MQTT_TOPICS", "rtl_433/#")
        topic_list = [
            topic.strip()
            for topic in topics.split(",")
            if topic.strip()
        ]

        return AppConfig(
            mqtt_host=os.getenv("MQTT_HOST", "localhost"),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_username=os.getenv("MQTT_USERNAME") or None,
            mqtt_password=os.getenv("MQTT_PASSWORD") or None,
            mqtt_topics=topic_list,
            mqtt_discriminator_path=os.getenv("MQTT_DISCRIMINATOR_PATH", "id"),
            mqtt_filter_path=os.getenv("MQTT_FILTER_PATH") or None,
            mqtt_filter_value=os.getenv("MQTT_FILTER_VALUE") or None,
            store_max_items=int(os.getenv("STORE_MAX_ITEMS", "1000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
