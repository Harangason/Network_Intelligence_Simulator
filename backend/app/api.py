"""HTTP endpoints for the simulator web application."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from psycopg import Error as DatabaseError

from .job_service import JOBS
from .config import RUNTIME_ROOT
from .trace_storage import StorageError, StorageUnavailable
from .runtime_config import runtime_status
from .build_info import build_info
from ..engineering.project_context import compact_context_project_id, normalize_context_project_id
from ..engineering.workflow.service import WorkflowStatusService, WorkflowConflictError
from ..engineering.simulation import create_campaign_record, get_campaign_record, update_campaign_record
from ..communication.technologies import DEFAULT_TECHNOLOGY_ONBOARDING, DEFAULT_TECHNOLOGY_REGISTRY as COMMUNICATION_TECHNOLOGY_REGISTRY


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
        "build": build_info(),
    }
    instance_id = os.environ.get("SIMULATOR_INSTANCE_ID")
    if instance_id:
        response["instance_id"] = instance_id
    return jsonify(response)


@api.get("/build-info")
def release_info():
    return jsonify(build_info())


@api.errorhandler(StorageError)
def storage_error(error):
    return jsonify({"error": str(error)}), 503 if isinstance(error, StorageUnavailable) else 400


@api.get("/storage/settings")
def storage_settings():
    return jsonify(JOBS.storage.settings(_request_project_id()))


@api.put("/storage/settings")
def save_storage_settings():
    # Deliberately not CORS-allowlisted: cross-origin sites cannot change local paths.
    if request.headers.get("X-NetworkIS-Storage") != "confirmed":
        return jsonify({"error": "Speicheränderung muss ausdrücklich bestätigt werden."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "path" not in payload:
        return jsonify({"error": "Ein JSON-Objekt mit path wird erwartet; null setzt den Standard zurück."}), 400
    return jsonify(JOBS.storage.save(_request_project_id(), payload["path"]))


@api.post("/storage/validate")
def validate_storage_settings():
    if request.headers.get("X-NetworkIS-Storage") != "confirmed":
        return jsonify({"error": "Die Schreibprüfung muss ausdrücklich angefordert werden."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt mit path wird erwartet."}), 400
    return jsonify(JOBS.storage.validate(payload.get("path")))


@api.get("/storage/directories")
def storage_directories():
    return jsonify(JOBS.storage.directories(_request_project_id(), request.args.get("path")))


@api.get('/ready')
def readiness():
    """Liveness alone cannot detect a broken Windows/Docker runtime mount."""
    try:
        if not RUNTIME_ROOT.is_dir() or not os.access(RUNTIME_ROOT, os.R_OK | os.W_OK):
            raise OSError('Laufzeitverzeichnis ist nicht les- und schreibbar.')
        from ..engineering.db import get_connection
        with get_connection() as connection:
            connection.execute('SELECT 1').fetchone()
    except (OSError, RuntimeError, DatabaseError) as error:
        return jsonify({'status': 'unavailable', 'error': str(error), 'service': 'communication-simulator'}), 503
    return jsonify({'status': 'ready', 'storage': 'available', 'database': 'available'})


@api.route("/technologies", methods=["GET"])
def technologies():
    return jsonify(JOBS.simulations.catalog())


@api.post("/technologies/resolve")
def resolve_technology_knowledge():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not (payload.get("technology") or payload.get("technology_id")):
        return jsonify({"error": "technology or technology_id is required"}), 400
    value = payload.get("technology_id") or payload.get("technology")
    return jsonify(DEFAULT_TECHNOLOGY_ONBOARDING.resolve(value, requested_revision=payload.get("revision")))


@api.post("/technologies/research")
def research_technology_knowledge():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not (payload.get("technology") or payload.get("technology_id")):
        return jsonify({"error": "technology or technology_id is required"}), 400
    value = payload.get("technology_id") or payload.get("technology")
    return jsonify(DEFAULT_TECHNOLOGY_ONBOARDING.research(value, triggers=payload.get("triggers") or ("unknown_protocol",)))


@api.post("/technologies/validate-parameters")
def validate_technology_parameters():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not (payload.get("technology") or payload.get("technology_id")):
        return jsonify({"error": "technology or technology_id is required"}), 400
    technology_id = payload.get("technology_id") or payload.get("technology")
    result = COMMUNICATION_TECHNOLOGY_REGISTRY.validate_parameters(technology_id, dict(payload.get("parameters") or {}))
    return jsonify(result), 422 if result["status"] == "INVALID" else 200


@api.post("/technologies/audit")
def audit_technology_parameters():
    payload = request.get_json(silent=True)
    bindings = payload.get("bindings") if isinstance(payload, dict) else None
    if not isinstance(bindings, list):
        return jsonify({"error": "bindings must be a list"}), 400
    findings = COMMUNICATION_TECHNOLOGY_REGISTRY.audit_bindings(bindings)
    return jsonify({"status": "INVALID" if findings else "VALID", "findings": findings})


@api.post("/technology-packs")
def create_technology_pack():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    try:
        pack = DEFAULT_TECHNOLOGY_ONBOARDING.create_pack(payload, persist=True)
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(pack), 201


@api.get("/technology-packs/<technology_id>")
def get_technology_pack(technology_id: str):
    try:
        pack = DEFAULT_TECHNOLOGY_ONBOARDING.load_pack(technology_id)
    except FileNotFoundError:
        return jsonify({"error": "Technology Pack not found."}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 409
    return jsonify(pack)


@api.post("/technology-packs/<technology_id>/register")
def register_technology_pack(technology_id: str):
    if request.headers.get("X-NIS-Technology-Registration") != "confirmed":
        return jsonify({"error": "Core registration must be explicitly confirmed."}), 403
    try:
        result = DEFAULT_TECHNOLOGY_ONBOARDING.register_pack(technology_id)
    except FileNotFoundError:
        return jsonify({"error": "Technology Pack not found."}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 409
    return jsonify(result)


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
    if snapshot_id:
        try:
            snapshot = WorkflowStatusService(project_id).claim_simulation_snapshot(str(snapshot_id))
        except WorkflowConflictError as error:
            return jsonify({"error": str(error)}), 409
        configuration = snapshot["configuration"]
        payload = {"config": configuration}
        payload.update(project_id=project_id, workflow_snapshot_id=snapshot_id, workflow_managed=True)
    try:
        job = JOBS.submit(payload)
    except Exception:
        if snapshot_id:
            WorkflowStatusService(project_id).update_simulation_snapshot(str(snapshot_id), status="FAILED")
        raise
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
    job = JOBS.get(job_id, project_id, metadata=request.args.get("view") == "metadata")
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


@api.route("/simulations/<job_id>", methods=["POST"])
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


@api.get('/simulations/<job_id>/trace-window')
def trace_window(job_id: str):
    from .trace_service import read_trace_window
    project_id = _request_project_id()
    job = JOBS.get(job_id, project_id, metadata=True)
    if job is None:
        return jsonify({'error': 'Simulation nicht gefunden.'}), 404
    artifacts = (job.get('result') or {}).get('artifacts') or []
    index = next((i for i, path in enumerate(artifacts) if str(path).endswith('universal_trace.jsonl')), None)
    if index is None:
        return jsonify({'error': 'Kein universeller JSONL-Trace vorhanden.'}), 404
    try:
        path = JOBS.artifact(job_id, index, project_id)
        if path is None:
            return jsonify({'error': 'Trace-Datei nicht gefunden.'}), 404
        result = read_trace_window(path, cursor=int(request.args.get('cursor', 0)),
                                  limit=int(request.args.get('limit', 500)),
                                  start_s=float(request.args.get('start_s', 0)),
                                  end_s=float(request.args.get('end_s', 1e15)),
                                  query=request.args.get('q', ''))
        return jsonify({**result, 'job_id': job_id, 'project_id': project_id})
    except (ValueError, UnicodeError) as error:
        return jsonify({'error': str(error)}), 400
    except OSError:
        return jsonify({'error': 'Trace-Speicher derzeit nicht erreichbar. Erneut versuchen.'}), 503


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
