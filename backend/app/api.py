"""HTTP endpoints for the simulator web application."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from .job_service import JOBS
from ..engineering.workflow.service import WorkflowStatusService


api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health():
    response = {"status": "ok", "service": "communication-simulator"}
    instance_id = os.environ.get("SIMULATOR_INSTANCE_ID")
    if instance_id:
        response["instance_id"] = instance_id
    return jsonify(response)


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
    snapshot_id = payload.get("workflow_snapshot_id")
    project_id = str(payload.get("project_id") or "default")
    if payload.get("workflow_managed") and not snapshot_id:
        return jsonify({"error": "Ein validierter SimulationSnapshot ist erforderlich."}), 409
    if snapshot_id:
        snapshot = WorkflowStatusService(project_id).get_simulation_snapshot(str(snapshot_id))
        if snapshot is None:
            return jsonify({"error": "SimulationSnapshot nicht gefunden."}), 404
        if snapshot["is_outdated"] or snapshot["status"] != "READY":
            return jsonify({"error": "Der SimulationSnapshot ist nicht mehr ausfuehrbar."}), 409
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


@api.route("/simulations/<job_id>/cancel", methods=["POST"])
def cancel_simulation(job_id: str):
    job = JOBS.cancel(job_id)
    if job is None:
        return jsonify({"error": "Simulation nicht gefunden."}), 404
    return jsonify(job)


@api.route("/simulations/<job_id>/artifacts/<int:artifact_index>", methods=["GET"])
def artifact(job_id: str, artifact_index: int):
    path = JOBS.artifact(job_id, artifact_index)
    if path is None:
        return jsonify({"error": "Artefakt nicht gefunden."}), 404
    return send_file(path, as_attachment=True, download_name=path.name)
