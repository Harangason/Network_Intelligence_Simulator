"""Flask application factory."""

from __future__ import annotations

import os
from flask import Flask, request

from ..engineering import engineering_api
from .api import api


def create_app(testing: bool = False, api_prefix: str = "/api") -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        JSON_SORT_KEYS=False,
    )
    app.register_blueprint(api, url_prefix=api_prefix)
    app.register_blueprint(engineering_api, url_prefix=f"{api_prefix}/engineering")

    @app.after_request
    def add_cors_headers(response):
        configured_origin = os.environ.get("FRONTEND_ORIGIN")
        request_origin = request.headers.get("Origin", "")
        local_origins = {"http://127.0.0.1:3500", "http://localhost:3500"}
        origin = configured_origin or (
            request_origin if request_origin in local_origins else "http://127.0.0.1:3500"
        )
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Project-ID"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        response.headers["Vary"] = "Origin"
        return response

    return app
