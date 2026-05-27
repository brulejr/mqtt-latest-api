import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "mqtt": {
        "host": "localhost",
        "port": 1883,
        "username": None,
        "password": None,
        "topics": ["rtl_433/#"],
        "discriminator_path": "id",
        "filter": {
            "path": None,
            "value": None,
        },
    },
    "store": {
        "max_items": 1000,
    },
    "logging": {
        "level": "INFO",
    },
}


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

    config_profiles: list[str]
    config_sources: list[str]

    @staticmethod
    def from_env() -> "AppConfig":
        merged = load_yaml_configuration()
        merged = apply_environment_overrides(merged)

        mqtt = merged.get("mqtt", {})
        mqtt_filter = mqtt.get("filter", {}) or {}
        store = merged.get("store", {})
        logging_config = merged.get("logging", {})

        topics = normalize_topics(mqtt.get("topics", ["rtl_433/#"]))
        profiles = parse_csv(os.getenv("CONFIG_PROFILES", os.getenv("APP_PROFILES", "")))

        return AppConfig(
            mqtt_host=str(mqtt.get("host", "localhost")),
            mqtt_port=int(mqtt.get("port", 1883)),
            mqtt_username=empty_to_none(mqtt.get("username")),
            mqtt_password=empty_to_none(mqtt.get("password")),
            mqtt_topics=topics,
            mqtt_discriminator_path=str(mqtt.get("discriminator_path", "id")),
            mqtt_filter_path=empty_to_none(mqtt_filter.get("path")),
            mqtt_filter_value=empty_to_none(mqtt_filter.get("value")),
            store_max_items=int(store.get("max_items", 1000)),
            log_level=str(logging_config.get("level", "INFO")),
            config_profiles=profiles,
            config_sources=merged.get("_config_sources", []),
        )


def load_yaml_configuration() -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    loaded_sources: list[str] = []

    profiles = parse_csv(os.getenv("CONFIG_PROFILES", os.getenv("APP_PROFILES", "")))
    locations = parse_csv(
        os.getenv(
            "CONFIG_LOCATIONS",
            "/app/app/config,/config,./config,.",
        )
    )

    for candidate in iter_config_files(locations=locations, profiles=profiles):
        if not candidate.exists() or not candidate.is_file():
            continue

        with candidate.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Configuration file must contain a YAML object: {candidate}")

        merged = deep_merge(merged, data)
        loaded_sources.append(str(candidate))

    merged["_config_sources"] = loaded_sources
    return merged


def iter_config_files(locations: list[str], profiles: list[str]) -> list[Path]:
    files: list[Path] = []

    for location in locations:
        path = Path(location)

        if path.suffix in {".yml", ".yaml"}:
            files.append(path)
            continue

        files.append(path / "application.yml")
        files.append(path / "application.yaml")

        for profile in profiles:
            files.append(path / f"application-{profile}.yml")
            files.append(path / f"application-{profile}.yaml")

    return files


def apply_environment_overrides(config: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(config)

    env_overrides: list[tuple[str, list[str], Any]] = [
        ("MQTT_HOST", ["mqtt", "host"], str),
        ("MQTT_PORT", ["mqtt", "port"], int),
        ("MQTT_USERNAME", ["mqtt", "username"], str),
        ("MQTT_PASSWORD", ["mqtt", "password"], str),
        ("MQTT_TOPICS", ["mqtt", "topics"], parse_csv),
        ("MQTT_DISCRIMINATOR_PATH", ["mqtt", "discriminator_path"], str),
        ("MQTT_FILTER_PATH", ["mqtt", "filter", "path"], str),
        ("MQTT_FILTER_VALUE", ["mqtt", "filter", "value"], str),
        ("STORE_MAX_ITEMS", ["store", "max_items"], int),
        ("LOG_LEVEL", ["logging", "level"], str),
    ]

    for env_name, path, converter in env_overrides:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            continue

        set_nested(result, path, converter(raw_value))

    return result


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)

    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def set_nested(target: dict[str, Any], path: list[str], value: Any) -> None:
    current = target

    for part in path[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value

    current[path[-1]] = value


def normalize_topics(value: Any) -> list[str]:
    if isinstance(value, str):
        return parse_csv(value)

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return ["rtl_433/#"]


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def empty_to_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)
    if text == "":
        return None

    return text
