"""HTTP endpoints for the simulator web application."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from .job_service import JOBS
from .runtime_config import runtime_status
from ..engineering.project_context import compact_context_project_id, normalize_context_project_id
from ..engineering.workflow.service import WorkflowStatusService
from ..engineering.simulation import create_campaign_record, get_campaign_record, update_campaign_record


api = Blueprint("api", __name__)


def _request_project_id() -> str:
    return normalize_context_project_id(
        request.args.get("project")
        or request.args.get("project_id")
        or request.args.get("projectId")
        or request.headers.get("X-Project-ID")
        or "default"
    )


def _payload_project_id(payload: dict, fallback: str = "default") -> str:
    return normalize_context_project_id(
        payload.get("project")
        or payload.get("project_id")
        or payload.get("projectId")
        or fallback
    )


def _explicit_project_id() -> str | None:
    raw = request.args.get("project") or request.args.get("project_id") or request.args.get("projectId") or request.headers.get("X-Project-ID")
    return normalize_context_project_id(raw) if raw else None


@api.route("/health", methods=["GET"])
def health():
    response = {
        "status": "ok",
        "service": "communication-simulator",
        "runtime": runtime_status(),
        "jobs": JOBS.runtime_summary(),
    }
    instance_id = os.environ.get("SIMULATOR_INSTANCE_ID")
    if instance_id:
        response["instance_id"] = instance_id
    return jsonify(response)


@api.route("/technologies", methods=["GET"])
def technologies():
    return jsonify(JOBS.simulations.catalog())


@api.route("/simulations", methods=["GET"])
def list_simulations():
    return jsonify({"jobs": JOBS.list(_request_project_id())})


@api.route("/simulations", methods=["POST"])
def create_simulation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    explicit_project_id = _explicit_project_id()
    request_project_id = normalize_context_project_id(explicit_project_id or _payload_project_id(payload))
    payload_project_id = _payload_project_id(payload, request_project_id)
    if explicit_project_id and payload_project_id != request_project_id:
        return jsonify({"error": "Projekt-ID in Header und Payload stimmt nicht überein."}), 409
    payload["project_id"] = request_project_id
    snapshot_id = payload.get("workflow_snapshot_id")
    project_id = request_project_id
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
    explicit_project_id = _explicit_project_id()
    request_project_id = normalize_context_project_id(explicit_project_id or _payload_project_id(payload))
    payload_project_id = _payload_project_id(payload, request_project_id)
    if explicit_project_id and payload_project_id != request_project_id:
        return jsonify({"error": "Projekt-ID in Header und Payload stimmt nicht überein."}), 409
    payload["project_id"] = request_project_id
    job = JOBS.submit(payload, validate_only=True)
    return jsonify(job), 202


@api.route("/simulations/<job_id>", methods=["GET"])
def simulation(job_id: str):
    project_id = _request_project_id()
    job = JOBS.get(job_id, project_id)
    if job is None:
        return jsonify({"error": "Simulation nicht gefunden."}), 404
    if job.get("result"):
        artifacts = job["result"].get("artifacts") or []
        job["artifact_downloads"] = [
            {
                "index": index,
                "name": Path(path).name,
                "url": f"/api/simulations/{job_id}/artifacts/{index}?project={compact_context_project_id(project_id)}",
            }
            for index, path in enumerate(artifacts)
        ]
    return jsonify(job)


@api.route("/simulations/<job_id>/cancel", methods=["POST"])
def cancel_simulation(job_id: str):
    job = JOBS.cancel(job_id, _request_project_id())
    if job is None:
        return jsonify({"error": "Simulation nicht gefunden."}), 404
    return jsonify(job)


@api.route("/simulations/<job_id>/artifacts/<int:artifact_index>", methods=["GET"])
def artifact(job_id: str, artifact_index: int):
    path = JOBS.artifact(job_id, artifact_index, _request_project_id())
    if path is None:
        return jsonify({"error": "Artefakt nicht gefunden."}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


@api.route("/simulation-campaigns", methods=["POST"])
def create_simulation_campaign():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein Kampagnen-Objekt wird erwartet."}), 400
    project_id = _payload_project_id(payload)
    workflow = WorkflowStatusService(project_id).get()
    if workflow.get("statuses", {}).get("validation") not in {"APPROVED", "WARNING"}:
        return jsonify({"error": "Eine aktuelle erfolgreiche Validierung ist für Kampagnen erforderlich."}), 409
    seeds = payload.get("seeds") if isinstance(payload.get("seeds"), list) else [42]
    scenarios = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else [{}]
    run_count = len(seeds) * len(scenarios)
    if run_count < 1 or run_count > 50:
        return jsonify({"error": "Eine Kampagne muss zwischen 1 und 50 Läufe enthalten."}), 400
    base_config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    runs = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            return jsonify({"error": "Jedes Kampagnenszenario muss ein Objekt sein."}), 400
        for seed in seeds:
            run_payload = {
                "project_id": project_id,
                "config": {**base_config, "seed": int(seed), "scenario": scenario},
                "scenario": scenario,
                "seed": int(seed),
            }
            job = JOBS.submit(run_payload)
            runs.append({"job_id": job["id"], "seed": int(seed), "scenario": scenario, "status": job["status"]})
    campaign = create_campaign_record(
        project_id,
        str(payload.get("name") or "Simulation campaign"),
        {"seeds": seeds, "scenarios": scenarios, "config": base_config},
        runs,
    )
    return jsonify(campaign), 202


@api.route("/simulation-campaigns/<campaign_id>", methods=["GET"])
def simulation_campaign(campaign_id: str):
    project_id = _request_project_id()
    campaign = get_campaign_record(project_id, campaign_id)
    if campaign is None:
        return jsonify({"error": "Simulationskampagne nicht gefunden."}), 404
    statuses = {
        str(run["job_id"]): str((JOBS.get(str(run["job_id"]), project_id) or {}).get("status") or run["status"])
        for run in campaign["runs"]
    }
    return jsonify(update_campaign_record(project_id, campaign_id, statuses))
