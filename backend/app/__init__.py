"""Flask application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify

from .api import api


def create_app(testing: bool = False, api_prefix: str = "/api") -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.register_blueprint(api, url_prefix=api_prefix)

    @app.after_request
    def add_cors_headers(response):
        origin = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:3001")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Die Anfrage ist größer als 2 MB."}), 413

    return app
