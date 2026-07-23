"""HTTP endpoints for the simulator web application."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from .job_service import JOBS


api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "communication-simulator"})


@api.route("/technologies", methods=["GET"])
def technologies():
    return jsonify(JOBS.simulations.catalog())


@api.route("/simulations", methods=["GET"])
def list_simulations():
    return jsonify({"jobs": JOBS.list()})


@api.route("/simulations", methods=["POST"])
def create_simulation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    job = JOBS.submit(payload)
    return jsonify(job), 202


@api.route("/simulations/validate", methods=["POST"])
def validate_simulation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    job = JOBS.submit(payload, validate_only=True)
    return jsonify(job), 202


@api.route("/simulations/<job_id>", methods=["GET"])
def simulation(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "Simulation nicht gefunden."}), 404
    if job.get("result"):
        artifacts = job["result"].get("artifacts") or []
        job["artifact_downloads"] = [
            {
                "index": index,
                "name": Path(path).name,
                "url": f"/api/simulations/{job_id}/artifacts/{index}",
            }
            for index, path in enumerate(artifacts)
        ]
    return jsonify(job)


@api.route("/simulations/<job_id>/artifacts/<int:artifact_index>", methods=["GET"])
def artifact(job_id: str, artifact_index: int):
    path = JOBS.artifact(job_id, artifact_index)
    if path is None:
        return jsonify({"error": "Artefakt nicht gefunden."}), 404
    return send_file(path, as_attachment=True, download_name=path.name)
