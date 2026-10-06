"""Flask application factory."""

from __future__ import annotations

import logging
import os
from flask import Flask, request

def __getattr__(name: str):
    """Retain public blueprint exports without initializing HTTP dependencies."""
    if name == "api":
        from backend.nis.interfaces.http.simulation import api
        return api
    if name == "engineering_api":
        from backend.nis.engineering import engineering_api
        return engineering_api
    raise AttributeError(name)


def create_app(testing: bool = False, api_prefix: str = "/api") -> Flask:
    from backend.nis.engineering import engineering_api
    from backend.nis.interfaces.http.simulation import api

    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        JSON_SORT_KEYS=False,
    )
    app.register_blueprint(api, url_prefix=api_prefix)
    from backend.nis.interfaces.http.trace_import import trace_import_api
    app.register_blueprint(trace_import_api, url_prefix=api_prefix)
    app.register_blueprint(engineering_api, url_prefix=f"{api_prefix}/engineering")
    from backend.nis.agent.tools.api import agent_api
    app.register_blueprint(agent_api, url_prefix=f"{api_prefix}/engineering/agent")

    if not testing:
        from backend.nis.simulation.job_service import JOBS
        # Readiness must include the complete catalog; a first browser request
        # must not spend its proxy deadline compiling every profile.
        JOBS.simulations.catalog_json()
        from backend.nis.engineering.goal_execution.background import start as start_goal_followups
        start_goal_followups()
        try:
            from backend.nis.agent.tools.run_status import recover_interrupted_wizard_runs
            recovered = recover_interrupted_wizard_runs()
            if recovered:
                logging.getLogger(__name__).warning(
                    "%s unterbrochene Wizard-Läufe für die Wiederaufnahme markiert.", recovered,
                )
        except Exception:
            # Keep health and diagnostics available when the database is the
            # dependency that prevented recovery.
            logging.getLogger(__name__).exception(
                "Unterbrochene Wizard-Läufe konnten beim Backend-Start nicht abgeglichen werden."
            )
        try:
            from backend.nis.simulation.job_service import JOBS
            recovered_jobs = JOBS.recover_interrupted()
            if recovered_jobs:
                logging.getLogger(__name__).warning('%s unterbrochene Simulationsjobs abgeglichen.', recovered_jobs)
        except Exception:
            logging.getLogger(__name__).exception('Simulationsjobs konnten beim Backend-Start nicht abgeglichen werden.')

    @app.after_request
    def add_cors_headers(response):
        configured_origin = os.environ.get("FRONTEND_ORIGIN")
        request_origin = request.headers.get("Origin", "")
        local_origins = {
            "http://127.0.0.1:13500",
            "http://localhost:13500",
            "http://127.0.0.1:13501",
            "http://localhost:13501",
        }
        origin = configured_origin or (
            request_origin if request_origin in local_origins else "http://127.0.0.1:13500"
        )
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Project-ID"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        response.headers["Vary"] = "Origin"
        return response

    return app
