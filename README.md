# MQTT Latest API

A small Flask application that ingests MQTT JSON messages, keeps only the latest message per discriminator key, and exposes the retained messages through a web API.

The application uses **Dynaconf's Flask extension** (`FlaskDynaconf`) for configuration datafill. `app.config` is the canonical Dynaconf-backed configuration object for the Flask application.

## Why FlaskDynaconf here?

Dynaconf's Flask integration replaces Flask's normal `app.config` object with a Dynaconf-backed config object. That gives the Flask app one canonical configuration source that supports settings files, environment variables, nested values, casting, validation, and extension-friendly access patterns.

This application initializes `FlaskDynaconf` inside the Flask application factory and then creates a small typed `AppConfig` adapter from `app.config` for the MQTT background component.

## Configuration model

Configuration is loaded in this order:

1. `application.yml` / `application.yaml` from each configured location.
2. `application-{profile}.yml` / `application-{profile}.yaml` from each configured location.
3. Dynaconf Flask environment variables using the `FLASK_` prefix.
4. Compatibility environment variables using the previous `APP_` prefix.
5. Legacy convenience environment variables such as `MQTT_HOST` and `MQTT_TOPICS`.

Later sources override earlier sources.

This keeps the Spring Boot-like profile overlay pattern while using FlaskDynaconf as the application configuration layer.

## Default config locations

By default, the application searches:

```text
/app/app/config
/config
./config
.
```

For each directory, it loads:

```text
application.yml
application.yaml
application-{profile}.yml
application-{profile}.yaml
```

## Selecting profiles

Use `CONFIG_PROFILES` with a comma-separated list:

```bash
CONFIG_PROFILES=local
```

or:

```bash
CONFIG_PROFILES=dev,site1
```

For example, with `CONFIG_PROFILES=local`, the app loads:

```text
application.yml
application-local.yml
```

from each configured config location, in order.

## Selecting config locations

Use `CONFIG_LOCATIONS` with comma-separated files or directories:

```bash
CONFIG_LOCATIONS=/app/app/config,/config
```

A directory location loads `application.yml` and profile-specific files. A file location loads that exact file.

## Example external override

Create this file on the host:

```text
./config/application-prod.yml
```

```yaml
mqtt:
  host: mosquitto.brulenet.dev
  port: 1883
  topics:
    - rtl_433/#
  discriminator_path: id
  filter:
    path: model
    value: Acurite-Tower

store:
  max_items: 2500

logging:
  level: INFO
```

Then run with:

```yaml
environment:
  CONFIG_PROFILES: prod
  CONFIG_LOCATIONS: /app/app/config,/config
volumes:
  - ./config:/config:ro
```

## Canonical FlaskDynaconf environment variable overrides

Use the `FLASK_` prefix and double underscores for nested fields:

```bash
FLASK_MQTT__HOST=mqtt
FLASK_MQTT__PORT=1883
FLASK_MQTT__DISCRIMINATOR_PATH=id
FLASK_MQTT__FILTER__PATH=model
FLASK_MQTT__FILTER__VALUE=Acurite-Tower
FLASK_STORE__MAX_ITEMS=2500
FLASK_LOGGING__LEVEL=INFO
```

For list values, use Dynaconf's type casting support:

```bash
FLASK_MQTT__TOPICS='@json ["rtl_433/#", "sensors/#"]'
```

## Compatibility environment variables

The prior `APP_` variables are still supported:

```bash
APP_MQTT__HOST=mqtt
APP_MQTT__PORT=1883
APP_MQTT__TOPICS='@json ["rtl_433/#", "sensors/#"]'
APP_STORE__MAX_ITEMS=2500
APP_LOGGING__LEVEL=INFO
```

The original convenience variables are also still supported:

```text
MQTT_HOST
MQTT_PORT
MQTT_USERNAME
MQTT_PASSWORD
MQTT_TOPICS
MQTT_DISCRIMINATOR_PATH
MQTT_FILTER_PATH
MQTT_FILTER_VALUE
STORE_MAX_ITEMS
LOG_LEVEL
CONFIG_PROFILES
CONFIG_LOCATIONS
```

`MQTT_TOPICS` is comma-separated when supplied as a legacy environment variable:

```bash
MQTT_TOPICS=rtl_433/#,sensors/#
```

## Build and run

```bash
docker compose up --build
```

## API

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/latest
curl http://localhost:8080/api/latest/12345
curl http://localhost:8080/api/config
```

## Operational note

The Dockerfile runs Gunicorn with one worker because the latest-message cache is in memory. If you later need multiple workers or multiple replicas, move the cache to Redis, MongoDB, or another shared backing store.
