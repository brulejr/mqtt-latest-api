# MQTT Latest API

A small Flask application that ingests MQTT JSON messages, keeps only the latest message per discriminator key, and exposes the retained messages through a web API.

## Configuration model

Configuration is loaded in this order:

1. Built-in defaults from the application.
2. `application.yml` files from configured locations.
3. `application-{profile}.yml` files from configured locations.
4. Environment variables.

Later sources override earlier sources. This is intentionally similar to Spring Boot's externalized configuration model.

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

## Environment variable overrides

These environment variables override YAML values:

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

`MQTT_TOPICS` is comma-separated when supplied as an environment variable:

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
