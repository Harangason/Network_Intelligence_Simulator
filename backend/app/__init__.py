"""Flask application factory."""

from __future__ import annotations

import os
import sys

from flask import Flask, jsonify

from .api import api
from .config import BACKEND_ROOT

# "engineering" lebt als Geschwister-Package neben "app" direkt unter
# backend/. Je nach Einstiegspunkt (main.py mit cwd=backend vs. Tests, die
# "backend" als Package von der Projektwurzel importieren) liegt backend/
# nicht immer schon auf sys.path - genau wie bei SIMULATOR_ROOT in
# simulation_service.py wird der Pfad hier bei Bedarf ergänzt.
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from engineering import engineering_api  # noqa: E402


def create_app(testing: bool = False, api_prefix: str = "/api") -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.register_blueprint(api, url_prefix=api_prefix)
    app.register_blueprint(engineering_api, url_prefix=f"{api_prefix}/engineering")

    @app.after_request
    def add_cors_headers(response):
        origin = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:3001")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,OPTIONS"
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Die Anfrage ist größer als 2 MB."}), 413

    return app
