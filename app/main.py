import atexit
import logging
import os

from flask import Flask

from app.config import AppConfig, init_config
from app.mqtt_client import MqttIngestClient
from app.routes import create_routes
from app.store import LatestMessageStore


def create_app() -> Flask:
    app = Flask(__name__)

    init_config(app)
    config = AppConfig.from_flask_config(app.config)

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logging.getLogger(__name__).info(
        "Loaded configuration profiles=%s sources=%s",
        config.config_profiles,
        config.config_sources,
    )

    store = LatestMessageStore(max_items=config.store_max_items)

    mqtt_client = MqttIngestClient(
        config=config,
        store=store,
    )

    app.register_blueprint(create_routes(config=config, store=store))

    if should_start_mqtt_client():
        mqtt_client.start()
        atexit.register(mqtt_client.stop)

    return app


def should_start_mqtt_client() -> bool:
    """
    Prevent duplicate MQTT startup when running Flask's development reloader.

    In Docker/Gunicorn this returns True.
    """
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return True

    if os.environ.get("FLASK_ENV") == "development":
        return False

    return True


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
    )
