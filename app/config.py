import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dynaconf import FlaskDynaconf, Validator
from flask import Flask


DEFAULT_CONFIG_LOCATIONS = "/app/config,/config,./config,."
DEFAULT_SETTINGS_FILE_NAMES = ("application.yml", "application.yaml")
CONFIG_FILE_SUFFIXES = {".yml", ".yaml", ".toml", ".json", ".ini", ".py"}


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
    config_locations: list[str]
    config_sources: list[str]

    @staticmethod
    def from_flask_config(config: Any) -> "AppConfig":
        """
        Build a small typed adapter over Flask's Dynaconf-backed app.config.

        The application should read through Flask's config object rather than
        creating a separate global Dynaconf settings instance. That keeps Flask
        extensions, route handlers, tests, and background components aligned on
        the same loaded configuration.
        """
        return AppConfig(
            mqtt_host=str(config.get("MQTT.HOST", "localhost")),
            mqtt_port=int(config.get("MQTT.PORT", 1883)),
            mqtt_username=empty_to_none(config.get("MQTT.USERNAME")),
            mqtt_password=empty_to_none(config.get("MQTT.PASSWORD")),
            mqtt_topics=normalize_topics(config.get("MQTT.TOPICS", ["rtl_433/#"])),
            mqtt_discriminator_path=str(config.get("MQTT.DISCRIMINATOR_PATH", "id")),
            mqtt_filter_path=empty_to_none(config.get("MQTT.FILTER.PATH")),
            mqtt_filter_value=empty_to_none(config.get("MQTT.FILTER.VALUE")),
            store_max_items=int(config.get("STORE.MAX_ITEMS", 1000)),
            log_level=str(config.get("LOGGING.LEVEL", "INFO")),
            config_profiles=list(config.get("CONFIG_PROFILES", [])),
            config_locations=list(config.get("CONFIG_LOCATIONS", [])),
            config_sources=list(config.get("CONFIG_SOURCES", [])),
        )


def init_config(app: Flask) -> FlaskDynaconf:
    """
    Configure Flask using Dynaconf's Flask extension.

    Best-practice choices used here:
      * FlaskDynaconf is initialized inside the Flask app factory.
      * app.config becomes the canonical Dynaconf-backed settings object.
      * FLASK_ is the canonical environment-variable prefix for overrides.
      * Settings are loaded from explicit files discovered before initialization.
      * Validators provide defaults and basic startup validation.
      * Legacy APP_ and non-prefixed environment variables are mapped explicitly
        after FlaskDynaconf loads so older Compose files continue to work.
    """
    profiles = selected_profiles()
    locations = selected_locations()
    settings_files = discover_settings_files(
        locations=locations,
        profiles=profiles,
    )

    flask_dynaconf = FlaskDynaconf(
        app,
        envvar_prefix="FLASK",
        settings_files=[str(path) for path in settings_files],
        environments=False,
        merge_enabled=True,
        load_dotenv=True,
        lowercase_read=True,
        validators=build_validators(),
    )

    # Metadata used by /api/config and startup logging.
    app.config.set("CONFIG_PROFILES", profiles, loader_identifier="application_metadata")
    app.config.set("CONFIG_LOCATIONS", locations, loader_identifier="application_metadata")
    app.config.set(
        "CONFIG_SOURCES",
        [str(path) for path in settings_files],
        loader_identifier="application_metadata",
    )

    apply_compatibility_environment_overrides(app.config)
    app.config.validators.validate()

    return flask_dynaconf


def build_validators() -> list[Validator]:
    return [
        Validator("MQTT.HOST", default="localhost"),
        Validator("MQTT.PORT", default=1883, cast=int),
        Validator("MQTT.TOPICS", default=["rtl_433/#"]),
        Validator("MQTT.DISCRIMINATOR_PATH", default="id"),
        Validator("MQTT.USERNAME", default=None),
        Validator("MQTT.PASSWORD", default=None),
        Validator("MQTT.FILTER.PATH", default=None),
        Validator("MQTT.FILTER.VALUE", default=None),
        Validator("STORE.MAX_ITEMS", default=1000, cast=int, gte=1),
        Validator("LOGGING.LEVEL", default="INFO"),
    ]


def selected_profiles() -> list[str]:
    return parse_csv(
        os.getenv(
            "CONFIG_PROFILES",
            os.getenv("FLASK_PROFILES", os.getenv("APP_PROFILES", "")),
        )
    )


def selected_locations() -> list[str]:
    return parse_csv(
        os.getenv(
            "CONFIG_LOCATIONS",
            os.getenv("FLASK_CONFIG_LOCATIONS", os.getenv("APP_CONFIG_LOCATIONS", DEFAULT_CONFIG_LOCATIONS)),
        )
    )


def discover_settings_files(
    locations: list[str],
    profiles: list[str],
) -> list[Path]:
    candidates: list[Path] = []

    for location in locations:
        path = Path(location)

        if path.suffix in CONFIG_FILE_SUFFIXES:
            candidates.append(path)
            continue

        for file_name in DEFAULT_SETTINGS_FILE_NAMES:
            candidates.append(path / file_name)

        for profile in profiles:
            candidates.append(path / f"application-{profile}.yml")
            candidates.append(path / f"application-{profile}.yaml")

    return [candidate for candidate in candidates if candidate.exists() and candidate.is_file()]


def apply_compatibility_environment_overrides(config: Any) -> None:
    """
    Canonical Dynaconf Flask overrides use the FLASK_ prefix, for example:

        FLASK_MQTT__HOST=mqtt
        FLASK_MQTT__PORT=1883
        FLASK_STORE__MAX_ITEMS=1000
        FLASK_LOGGING__LEVEL=INFO
        FLASK_MQTT__TOPICS='@json ["rtl_433/#", "sensors/#"]'

    This function preserves the APP_ variables from the previous project ZIP and
    the original convenience variables from the first version of the project.
    """
    mappings: list[tuple[str, str, Any]] = [
        ("MQTT_HOST", "MQTT.HOST", str),
        ("MQTT_PORT", "MQTT.PORT", int),
        ("MQTT_USERNAME", "MQTT.USERNAME", str),
        ("MQTT_PASSWORD", "MQTT.PASSWORD", str),
        ("MQTT_TOPICS", "MQTT.TOPICS", parse_csv),
        ("MQTT_DISCRIMINATOR_PATH", "MQTT.DISCRIMINATOR_PATH", str),
        ("MQTT_FILTER_PATH", "MQTT.FILTER.PATH", str),
        ("MQTT_FILTER_VALUE", "MQTT.FILTER.VALUE", str),
        ("STORE_MAX_ITEMS", "STORE.MAX_ITEMS", int),
        ("LOG_LEVEL", "LOGGING.LEVEL", str),
        ("APP_MQTT__HOST", "MQTT.HOST", str),
        ("APP_MQTT__PORT", "MQTT.PORT", int),
        ("APP_MQTT__USERNAME", "MQTT.USERNAME", str),
        ("APP_MQTT__PASSWORD", "MQTT.PASSWORD", str),
        ("APP_MQTT__TOPICS", "MQTT.TOPICS", parse_topics_env_value),
        ("APP_MQTT__DISCRIMINATOR_PATH", "MQTT.DISCRIMINATOR_PATH", str),
        ("APP_MQTT__FILTER__PATH", "MQTT.FILTER.PATH", str),
        ("APP_MQTT__FILTER__VALUE", "MQTT.FILTER.VALUE", str),
        ("APP_STORE__MAX_ITEMS", "STORE.MAX_ITEMS", int),
        ("APP_LOGGING__LEVEL", "LOGGING.LEVEL", str),
    ]

    for env_name, key, converter in mappings:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            continue

        config.set(
            key,
            converter(raw_value),
            loader_identifier="compatibility_environment",
        )


def normalize_topics(value: Any) -> list[str]:
    if isinstance(value, str):
        return parse_topics_env_value(value)

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]

    return ["rtl_433/#"]


def parse_topics_env_value(value: str) -> list[str]:
    """
    Parse compatibility topic values.

    FLASK_MQTT__TOPICS should normally use Dynaconf casting, e.g.
    '@json ["rtl_433/#"]', which FlaskDynaconf handles before this function.
    APP_MQTT__TOPICS and MQTT_TOPICS are compatibility values and are treated as
    either comma-separated strings or a very small JSON list convenience form.
    """
    stripped = value.strip()

    if stripped.startswith("@json "):
        stripped = stripped.removeprefix("@json ").strip()

    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            import json

            parsed = json.loads(stripped)
            return normalize_topics(parsed)
        except Exception:
            return parse_csv(value)

    return parse_csv(value)


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def empty_to_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)
    if text == "" or text.lower() == "none":
        return None

    return text
