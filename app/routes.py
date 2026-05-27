from flask import Blueprint, jsonify

from app.config import AppConfig
from app.store import LatestMessageStore


def create_routes(
    config: AppConfig,
    store: LatestMessageStore,
) -> Blueprint:
    bp = Blueprint("api", __name__)

    @bp.get("/health")
    def health():
        return jsonify(
            {
                "status": "UP",
                "stored_items": store.count(),
            }
        )

    @bp.get("/api/latest")
    def list_latest():
        return jsonify(
            {
                "count": store.count(),
                "items": store.list_items(),
            }
        )

    @bp.get("/api/latest/<key>")
    def get_latest(key: str):
        item = store.get_item(key)

        if item is None:
            return jsonify(
                {
                    "error": "not_found",
                    "message": f"No item found for key: {key}",
                }
            ), 404

        return jsonify(item)

    @bp.get("/api/config")
    def get_config():
        return jsonify(
            {
                "mqtt_host": config.mqtt_host,
                "mqtt_port": config.mqtt_port,
                "mqtt_topics": config.mqtt_topics,
                "mqtt_discriminator_path": config.mqtt_discriminator_path,
                "mqtt_filter_path": config.mqtt_filter_path,
                "mqtt_filter_value": config.mqtt_filter_value,
                "store_max_items": config.store_max_items,
                "log_level": config.log_level,
                "config_profiles": config.config_profiles,
                "config_sources": config.config_sources,
            }
        )

    return bp
