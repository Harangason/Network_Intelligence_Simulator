"""Project-scoped behavior, scenario, fault proposal, and trace persistence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .models import EngineeringValidationError
from .project_context import activate_project, current_project_id, reset_project
from .repository import list_objects
from .routing.repository import list_routes

try:
    from simulator.signals.core.validation import validate_signal_emulation_model
except ImportError:  # pragma: no cover - package import fallback
    from backend.simulator.signals.core.validation import validate_signal_emulation_model


SCENARIO_MODES = {"NORMAL", "USER_DEFINED_FAULT", "AI_GENERATED_FAULT", "STRESS"}
SIGNAL_FAULTS = {
    "SIGNAL_STUCK", "SIGNAL_OFFSET", "SIGNAL_DRIFT", "SIGNAL_SPIKE", "SIGNAL_DROPOUT", "SIGNAL_NOISE",
    "SIGNAL_OUT_OF_RANGE", "SIGNAL_FROZEN", "SIGNAL_DELAYED", "SIGNAL_WRONG_SCALE", "SIGNAL_INVALID_VALUE",
}
MESSAGE_FAULTS = {
    "MESSAGE_LOSS", "MESSAGE_DELAY", "MESSAGE_JITTER", "MESSAGE_DUPLICATION", "MESSAGE_CORRUPTION", "MESSAGE_WRONG_CYCLE",
    "MESSAGE_TIMEOUT", "BURST_TRAFFIC", "FRAME_ERROR", "ROUTING_FAILURE",
}
NETWORK_FAULTS = {
    "NETWORK_OVERLOAD", "BUS_OFF", "LINK_DOWN", "GATEWAY_DELAY", "GATEWAY_DROP",
    "QUEUE_OVERFLOW", "CONGESTION", "TEMPORARY_DISCONNECT",
}
FAULTS_BY_SCOPE = {"SIGNAL": SIGNAL_FAULTS, "MESSAGE": MESSAGE_FAULTS, "NETWORK": NETWORK_FAULTS}
FAULT_ALIASES = {
    **{name.removeprefix("SIGNAL_"): name for name in SIGNAL_FAULTS},
    **{name.removeprefix("MESSAGE_"): name for name in MESSAGE_FAULTS if name.startswith("MESSAGE_")},
    "OVERLOAD": "NETWORK_OVERLOAD",
}


def _list_behaviors() -> list[dict[str, Any]]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_signal_behaviors WHERE project_id = %s ORDER BY modified_at DESC",
            (current_project_id(),),
        ).fetchall()


def load_engineering_simulation_model(project_id: str) -> dict[str, Any]:
    token = activate_project(project_id)
    try:
        nodes = list_objects("HardwareNode", limit=500)
        functions = list_objects("Function", limit=500)
        interfaces = list_objects("Interface", limit=500)
        messages = list_objects("Message", limit=500)
        signals = list_objects("Signal", limit=2000)
        routes = list_routes(limit=500)
        return {
            "schema": "communication-simulator.engineering-model.v1",
            "project_id": project_id,
            "nodes": nodes,
            "functions": functions,
            "interfaces": interfaces,
            "messages": messages,
            "signals": signals,
            "routes": routes,
            "behaviors": _list_behaviors(),
            "counts": {
                "nodes": len(nodes), "functions": len(functions), "interfaces": len(interfaces),
                "messages": len(messages), "signals": len(signals), "routes": len(routes),
            },
        }
    finally:
        reset_project(token)


def _load_project_transport_config(project_id: str, routes: list[dict[str, Any]]) -> dict[str, Any]:
    from .routing.config_builder import CommunicationConfigBuilder

    token = activate_project(project_id)
    try:
        return CommunicationConfigBuilder().build(routes).get("config") or {}
    finally:
        reset_project(token)


def enrich_simulation_config(config: dict[str, Any], project_id: str) -> dict[str, Any]:
    enriched = deepcopy(config)
    model = load_engineering_simulation_model(project_id)
    enriched["engineering_model"] = model
    if not enriched.get("communications"):
        transport = _load_project_transport_config(project_id, model["routes"])
        for key in ("networks", "hardware", "communications", "routing_entry_ids"):
            if not enriched.get(key) and transport.get(key):
                enriched[key] = deepcopy(transport[key])
    if not enriched.get("topology") or not enriched.get("parameters"):
        from .workflow.service import WorkflowStatusService

        workflow = WorkflowStatusService(project_id).get()
        if not enriched.get("topology"):
            enriched["topology"] = deepcopy(workflow.get("topology") or {})
        if not enriched.get("parameters"):
            enriched["parameters"] = deepcopy(workflow.get("parameters") or {})
    if model["routes"] and not enriched.get("communications"):
        raise EngineeringValidationError(
            "Das Projekt enthält keine freigegebenen ausführbaren Kommunikationspfade."
        )
    route_by_id = {str(item.get("id")): item for item in model["routes"]}
    topology = enriched.get("topology") if isinstance(enriched.get("topology"), dict) else {}
    node_engineering = {
        str(item.get("id")): str(item.get("engineeringId") or item.get("engineering_id") or "")
        for item in topology.get("nodes") or [] if isinstance(item, dict)
    }
    routes_by_source: dict[str, list[dict[str, Any]]] = {}
    for route in model["routes"]:
        source = route.get("source") if isinstance(route.get("source"), dict) else {}
        routes_by_source.setdefault(str(source.get("node_id") or ""), []).append(route)
    messages_by_interface: dict[str, list[str]] = {}
    for message in model["messages"]:
        messages_by_interface.setdefault(str(message.get("interface_id") or ""), []).append(str(message.get("id")))
    signals_by_message: dict[str, list[str]] = {}
    for signal in model["signals"]:
        signals_by_message.setdefault(str(signal.get("message_id") or ""), []).append(str(signal.get("id")))

    communications = enriched.get("communications") if isinstance(enriched.get("communications"), list) else []
    for communication in communications:
        if not isinstance(communication, dict):
            continue
        route_ids = [
            str(item) for item in communication.get("routing_entry_ids") or []
        ] if isinstance(communication.get("routing_entry_ids"), list) else []
        direct_route_id = str(communication.get("routing_entry_id") or "")
        if direct_route_id:
            route_ids.append(direct_route_id)
        linked_routes = [route_by_id[item] for item in route_ids if item in route_by_id]
        if not linked_routes:
            source_engineering_id = node_engineering.get(str(communication.get("source") or ""), "")
            linked_routes = routes_by_source.get(source_engineering_id, [])
        signal_ids = {
            str(signal_id)
            for route in linked_routes
            for signal_id in ((route.get("payload") or {}).get("signal_ids") or [])
        }
        message_ids = {
            str(message_id)
            for route in linked_routes
            for message_id in [
                *((route.get("payload") or {}).get("message_ids") or []),
                *(([(route.get("payload") or {}).get("message_id")]) if (route.get("payload") or {}).get("message_id") else []),
            ]
            if message_id
        }
        if not signal_ids:
            for message_id in message_ids:
                signal_ids.update(signals_by_message.get(message_id, []))
        if not signal_ids:
            sender_interface = str(communication.get("sender_interface") or communication.get("source_interface") or "")
            for message_id in messages_by_interface.get(sender_interface, []):
                signal_ids.update(signals_by_message.get(message_id, []))
                message_ids.add(message_id)
        if signal_ids:
            communication["signal_ids"] = sorted(signal_ids)
        if message_ids:
            communication["message_ids"] = sorted(message_ids)
        if linked_routes:
            communication["routing_entry_ids"] = sorted(str(route.get("id")) for route in linked_routes)
    _apply_simulation_scope(enriched)
    signal_validation = validate_signal_emulation_model(enriched)
    enriched["signal_emulation_validation"] = signal_validation
    if not signal_validation["valid"]:
        first_error = signal_validation["errors"][0]["message"] if signal_validation["errors"] else "ungueltige Signal-Emulation"
        raise EngineeringValidationError(f"Signal-Emulation Preflight fehlgeschlagen: {first_error}")
    return enriched


def _scope_values(raw: Any) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item)}


def _simulation_scope(config: dict[str, Any]) -> dict[str, Any]:
    scenario = config.get("scenario") if isinstance(config.get("scenario"), dict) else {}
    scope = scenario.get("simulation_scope") or config.get("simulation_scope") or {}
    return scope if isinstance(scope, dict) else {}


def _apply_simulation_scope(config: dict[str, Any]) -> None:
    scope = _simulation_scope(config)
    if not scope or bool(scope.get("include_all")) or str(scope.get("mode") or "ALL").upper() == "ALL":
        return
    selected_message_ids = _scope_values(scope.get("message_ids"))
    selected_signal_ids = _scope_values(scope.get("signal_ids"))
    if not selected_message_ids and not selected_signal_ids:
        return

    model = config.get("engineering_model") if isinstance(config.get("engineering_model"), dict) else {}
    messages = [item for item in model.get("messages") or [] if isinstance(item, dict)]
    signals = [item for item in model.get("signals") or [] if isinstance(item, dict)]
    message_by_id = {str(item.get("id")): item for item in messages}
    signals_by_message: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        signals_by_message.setdefault(str(signal.get("message_id") or ""), []).append(signal)

    if selected_signal_ids:
        selected_signal_rows = [item for item in signals if str(item.get("id")) in selected_signal_ids]
        selected_message_ids.update(str(item.get("message_id")) for item in selected_signal_rows if item.get("message_id"))
    if selected_message_ids and not selected_signal_ids:
        for message_id in selected_message_ids:
            selected_signal_ids.update(str(item.get("id")) for item in signals_by_message.get(message_id, []) if item.get("id"))

    selected_message_ids = {item for item in selected_message_ids if item in message_by_id}
    selected_signal_ids = {item for item in selected_signal_ids if any(str(signal.get("id")) == item for signal in signals)}
    if not selected_message_ids and not selected_signal_ids:
        return

    model["messages"] = [item for item in messages if str(item.get("id")) in selected_message_ids]
    model["signals"] = [item for item in signals if str(item.get("id")) in selected_signal_ids]
    counts = model.get("counts") if isinstance(model.get("counts"), dict) else {}
    counts["messages"] = len(model["messages"])
    counts["signals"] = len(model["signals"])
    model["counts"] = counts

    communications = config.get("communications") if isinstance(config.get("communications"), list) else []
    filtered_communications: list[dict[str, Any]] = []
    for communication in communications:
        if not isinstance(communication, dict):
            continue
        communication_message_ids = _scope_values(communication.get("message_ids"))
        communication_signal_ids = _scope_values(communication.get("signal_ids"))
        message_match = bool(communication_message_ids & selected_message_ids)
        signal_match = bool(communication_signal_ids & selected_signal_ids)
        if not message_match and not signal_match:
            continue
        if communication_message_ids:
            communication["message_ids"] = sorted(communication_message_ids & selected_message_ids)
        if communication_signal_ids:
            communication["signal_ids"] = sorted(communication_signal_ids & selected_signal_ids)
        filtered_communications.append(communication)
    config["communications"] = filtered_communications


def validate_scenario(scenario: dict[str, Any], engineering_model: dict[str, Any] | None = None) -> dict[str, Any]:
    mode = str(scenario.get("mode") or "NORMAL").upper()
    if mode not in SCENARIO_MODES:
        raise EngineeringValidationError(f"Unbekannter Simulationsmodus: {mode}")
    faults = scenario.get("faults") if isinstance(scenario.get("faults"), list) else []
    if mode == "NORMAL" and faults:
        raise EngineeringValidationError("NORMAL darf keine absichtlich injizierten Fehler enthalten.")
    engineering_model = engineering_model or {}
    valid_targets = {
        "SIGNAL": {str(value) for item in engineering_model.get("signals") or [] if isinstance(item, dict) for value in (item.get("id"), item.get("name")) if value},
        "MESSAGE": {str(value) for item in engineering_model.get("messages") or [] if isinstance(item, dict) for value in (item.get("id"), item.get("name")) if value}
        | {str(value) for item in engineering_model.get("routes") or [] if isinstance(item, dict) for value in (item.get("id"), item.get("name")) if value},
        "NETWORK": {
            str((item.get("source") or {}).get("network_id"))
            for item in engineering_model.get("routes") or []
            if isinstance(item, dict) and isinstance(item.get("source"), dict) and (item.get("source") or {}).get("network_id")
        },
    }
    normalized = []
    for index, fault in enumerate(faults):
        if not isinstance(fault, dict):
            raise EngineeringValidationError(f"Fault {index + 1} muss ein Objekt sein.")
        scope = str(fault.get("scope") or "SIGNAL").upper()
        fault_type = FAULT_ALIASES.get(str(fault.get("type") or "").upper(), str(fault.get("type") or "").upper())
        if scope not in FAULTS_BY_SCOPE or fault_type not in FAULTS_BY_SCOPE[scope]:
            raise EngineeringValidationError(f"Fault {index + 1} ist für Scope {scope} nicht zulässig: {fault_type}")
        if str(fault.get("source") or "").lower() in {"ai", "ai_generated"} and not fault.get("approved"):
            raise EngineeringValidationError("KI-Fehler dürfen erst nach expliziter Annahme aktiviert werden.")
        start_s = float(fault.get("start_s") or fault.get("start_time") or 0)
        if start_s < 0:
            raise EngineeringValidationError(f"Fault {index + 1} hat eine negative Startzeit.")
        end_value = fault.get("end_s")
        if end_value is None and fault.get("duration") is not None:
            end_value = start_s + float(fault["duration"])
        end_s = float(end_value) if end_value is not None else None
        if end_s is not None and end_s <= start_s:
            raise EngineeringValidationError(f"Fault {index + 1} muss nach seiner Startzeit enden.")
        target = fault.get("target") if isinstance(fault.get("target"), dict) else {}
        target_id = str(target.get("id") or target.get("name") or "")
        if target_id and valid_targets[scope] and target_id not in valid_targets[scope]:
            raise EngineeringValidationError(f"Fault {index + 1} referenziert kein vorhandenes {scope}-Ziel: {target_id}")
        normalized.append({
            **fault,
            "scope": scope,
            "type": fault_type,
            "start_s": start_s,
            **({"end_s": end_s} if end_s is not None else {}),
            "model_fidelity": "SIMPLIFIED_FAULT_MODEL" if scope == "NETWORK" else "RULE_BASED",
        })
    return {**scenario, "mode": mode, "faults": normalized}


class FaultScenarioValidator:
    def validate(self, scenario: dict[str, Any], engineering_model: dict[str, Any] | None = None) -> dict[str, Any]:
        return validate_scenario(scenario, engineering_model)


def list_scenarios() -> list[dict[str, Any]]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_simulation_scenarios WHERE project_id = %s ORDER BY modified_at DESC",
            (current_project_id(),),
        ).fetchall()


def save_scenario(data: dict[str, Any]) -> dict[str, Any]:
    scenario = validate_scenario(data)
    with get_connection() as connection:
        row = connection.execute(
            "INSERT INTO engineering_simulation_scenarios "
            "(project_id, name, description, mode, duration_s, speed, seed, trace_formats, simulation_scope, faults, "
            "initial_conditions, signal_profiles, expected_behavior, source, review_state, approval_state, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                current_project_id(), str(scenario.get("name") or "Simulationsszenario"), scenario.get("description"), scenario["mode"],
                float(scenario.get("duration_s") or 1), float(scenario.get("speed") or 1), int(scenario.get("seed") or 42),
                Jsonb(scenario.get("trace_formats") or ["universal-jsonl"]), Jsonb(scenario.get("simulation_scope") or {}),
                Jsonb(scenario.get("faults") or []),
                Jsonb(scenario.get("initial_conditions") or {}), Jsonb(scenario.get("signal_profiles") or []),
                Jsonb(scenario.get("expected_behavior") or {}), str(scenario.get("source") or "manual"),
                "reviewed", "approved", scenario.get("created_by") or "simulation-user",
            ),
        ).fetchone()
        connection.commit()
    return row


def list_fault_proposals() -> list[dict[str, Any]]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_fault_proposals WHERE project_id = %s ORDER BY created_at DESC",
            (current_project_id(),),
        ).fetchall()


def propose_faults() -> list[dict[str, Any]]:
    signals = list_objects("Signal", limit=500)
    messages = list_objects("Message", limit=500)
    routes = list_routes(limit=500)
    candidates: list[dict[str, Any]] = []
    if signals:
        signals_by_id = {str(item.get("id")): item for item in signals}
        routed_signal_ids = [
            str(signal_id)
            for route in routes
            for signal_id in ((route.get("payload") or {}).get("signal_ids") or [])
        ]
        signal = next(
            (signals_by_id[signal_id] for signal_id in routed_signal_ids if signal_id in signals_by_id),
            signals[0],
        )
        candidates.append({
            "title": f"Rauschen auf {signal.get('name')}", "scope": "SIGNAL", "type": "SIGNAL_NOISE",
            "target": {"id": str(signal.get("id")), "name": signal.get("name")},
            "configuration": {"magnitude": max(0.1, abs(float(signal.get("max_value") or 100) - float(signal.get("min_value") or 0)) * 0.03), "start_s": 0.2},
            "rationale": "Prüft Robustheit und Grenzwertlogik gegen plausibles Messrauschen.",
            "evidence": [{"kind": "signal_definition", "id": str(signal.get("id"))}],
            "expected_effect": {"signal_deviation": True, "network_transport": "unchanged"},
            "confidence": 0.82,
        })
    if messages:
        messages_by_id = {str(item.get("id")): item for item in messages}
        routed_message_ids = [
            str(message_id)
            for route in routes
            for message_id in [
                *((route.get("payload") or {}).get("message_ids") or []),
                *(([(route.get("payload") or {}).get("message_id")]) if (route.get("payload") or {}).get("message_id") else []),
            ]
            if message_id
        ]
        message = next(
            (messages_by_id[message_id] for message_id in routed_message_ids if message_id in messages_by_id),
            messages[0],
        )
        candidates.append({
            "title": f"Verlust von {message.get('name')}", "scope": "MESSAGE", "type": "MESSAGE_LOSS",
            "target": {"id": str(message.get("id")), "name": message.get("name")},
            "configuration": {"start_s": 0.35, "end_s": 0.55},
            "rationale": "Prüft Timeout- und Ersatzwertreaktionen des Empfängers.",
            "evidence": [{"kind": "message_definition", "id": str(message.get("id"))}],
            "expected_effect": {"timeout_or_stale_signal": True, "packet_loss": 1.0},
            "confidence": 0.88,
        })
    if routes:
        route = routes[0]
        source = route.get("source") if isinstance(route.get("source"), dict) else {}
        candidates.append({
            "title": "Temporäre Netzüberlast", "scope": "NETWORK", "type": "NETWORK_OVERLOAD",
            "target": {"id": str(source.get("network_id") or "")},
            "configuration": {"factor": 4, "start_s": 0.4, "end_s": 0.7},
            "rationale": "Prüft Queue-, Peak- und Burst-Verhalten auf dem freigegebenen Pfad.",
            "evidence": [{"kind": "routing_entry", "id": str(route.get("id"))}],
            "expected_effect": {"peak_load_increase": True, "queue_delay_increase": True},
            "confidence": 0.76,
        })
    created = []
    with get_connection() as connection:
        for candidate in candidates:
            created.append(connection.execute(
                "INSERT INTO engineering_fault_proposals "
                "(project_id, title, fault_scope, fault_type, target, configuration, rationale, evidence, "
                "expected_effect, confidence, origin, model, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AI_GENERATED', %s, 'READY_FOR_REVIEW') RETURNING *",
                (
                    current_project_id(), candidate["title"], candidate["scope"], candidate["type"],
                    Jsonb(candidate["target"]), Jsonb(candidate["configuration"]), candidate["rationale"],
                    Jsonb(candidate["evidence"]), Jsonb(candidate["expected_effect"]), candidate["confidence"],
                    "deterministic-engineering-agent-v1",
                ),
            ).fetchone())
        connection.commit()
    return created


def review_fault_proposal(proposal_id: str, action: str, actor: str | None = None, changes: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_action = action.upper()
    status = {"ACCEPT": "APPROVED", "REJECT": "REJECTED", "EDIT": "READY_FOR_REVIEW"}.get(normalized_action)
    if not status:
        raise EngineeringValidationError("action muss ACCEPT, EDIT oder REJECT sein.")
    changes = changes or {}
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_fault_proposals SET status = %s, configuration = COALESCE(%s, configuration), "
            "target = COALESCE(%s, target), reviewed_by = %s, modified_at = now() "
            "WHERE proposal_id = %s AND project_id = %s RETURNING *",
            (
                status,
                Jsonb(changes["configuration"]) if isinstance(changes.get("configuration"), dict) else None,
                Jsonb(changes["target"]) if isinstance(changes.get("target"), dict) else None,
                actor, proposal_id, current_project_id(),
            ),
        ).fetchone()
        if row is None:
            raise EngineeringValidationError("Fault-Vorschlag nicht gefunden.")
        connection.commit()
    return row


def persist_trace_metadata(project_id: str, job_id: str, result: dict[str, Any], config: dict[str, Any]) -> None:
    token = activate_project(project_id)
    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO engineering_trace_metadata "
                "(project_id, job_id, simulation_id, scenario_id, scenario_type, scenario_snapshot, engineering_snapshot, "
                "model_versions, seed, trace_formats, artifact_paths, trace_summary, started_at, duration_s, networks, faults) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s) "
                "ON CONFLICT (project_id, job_id) DO UPDATE SET "
                "scenario_snapshot = EXCLUDED.scenario_snapshot, model_versions = EXCLUDED.model_versions, "
                "seed = EXCLUDED.seed, trace_formats = EXCLUDED.trace_formats, artifact_paths = EXCLUDED.artifact_paths, "
                "trace_summary = EXCLUDED.trace_summary, scenario_id = EXCLUDED.scenario_id, "
                "scenario_type = EXCLUDED.scenario_type, engineering_snapshot = EXCLUDED.engineering_snapshot, "
                "duration_s = EXCLUDED.duration_s, networks = EXCLUDED.networks, faults = EXCLUDED.faults",
                (
                    project_id, job_id, job_id, str((config.get("scenario") or {}).get("scenario_id") or ""),
                    str((config.get("scenario") or {}).get("mode") or "NORMAL"), Jsonb(config.get("scenario") or {}),
                    Jsonb((config.get("engineering_model") or {}).get("counts") or {}),
                    Jsonb({"behavior_engine": "v1", "codec": "v1", "fault_engine": "v1"}),
                    int(config.get("seed") or 42), Jsonb(config.get("formats") or []),
                    Jsonb(result.get("artifacts") or []), Jsonb({
                        "trace": result.get("trace") or {}, "runtime_metrics": result.get("runtime_metrics") or {},
                        "comparison": (result.get("model_simulation") or {}).get("comparison") or {},
                    }),
                    float(config.get("duration_s") or 1),
                    Jsonb([str(item.get("id")) for item in config.get("networks") or [] if isinstance(item, dict)]),
                    Jsonb((config.get("scenario") or {}).get("faults") or []),
                ),
            )
            connection.commit()
    finally:
        reset_project(token)


def trace_metadata(job_id: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as connection:
        if job_id:
            return connection.execute(
                "SELECT * FROM engineering_trace_metadata WHERE project_id = %s AND job_id = %s",
                (current_project_id(), job_id),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM engineering_trace_metadata WHERE project_id = %s ORDER BY created_at DESC LIMIT 100",
            (current_project_id(),),
        ).fetchall()


def artifact_job_id(output_dir: Path) -> str:
    return output_dir.resolve().name


def create_campaign_record(
    project_id: str,
    name: str,
    configuration: dict[str, Any],
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    token = activate_project(project_id)
    try:
        with get_connection() as connection:
            campaign = connection.execute(
                "INSERT INTO engineering_simulation_campaigns "
                "(project_id, name, configuration, total_runs) VALUES (%s, %s, %s, %s) RETURNING *",
                (project_id, name, Jsonb(configuration), len(runs)),
            ).fetchone()
            for run in runs:
                connection.execute(
                    "INSERT INTO engineering_simulation_campaign_runs "
                    "(campaign_id, job_id, seed, scenario_snapshot, status) VALUES (%s, %s, %s, %s, %s)",
                    (
                        campaign["campaign_id"], str(run["job_id"]), int(run["seed"]),
                        Jsonb(run.get("scenario") or {}), str(run.get("status") or "queued"),
                    ),
                )
            connection.commit()
        return {**campaign, "runs": runs}
    finally:
        reset_project(token)


def get_campaign_record(project_id: str, campaign_id: str) -> dict[str, Any] | None:
    token = activate_project(project_id)
    try:
        with get_connection() as connection:
            campaign = connection.execute(
                "SELECT * FROM engineering_simulation_campaigns WHERE project_id = %s AND campaign_id = %s",
                (project_id, campaign_id),
            ).fetchone()
            if campaign is None:
                return None
            runs = connection.execute(
                "SELECT * FROM engineering_simulation_campaign_runs WHERE campaign_id = %s ORDER BY created_at, job_id",
                (campaign_id,),
            ).fetchall()
        return {**campaign, "runs": runs}
    finally:
        reset_project(token)


def update_campaign_record(project_id: str, campaign_id: str, statuses: dict[str, str]) -> dict[str, Any] | None:
    token = activate_project(project_id)
    try:
        values = list(statuses.values())
        terminal = {"completed", "failed", "canceled"}
        complete = bool(values) and all(value in terminal for value in values)
        if not complete:
            campaign_status = "RUNNING"
        elif all(value == "completed" for value in values):
            campaign_status = "COMPLETED"
        elif all(value == "failed" for value in values):
            campaign_status = "FAILED"
        elif all(value == "canceled" for value in values):
            campaign_status = "CANCELED"
        else:
            campaign_status = "PARTIAL"
        with get_connection() as connection:
            for job_id, status in statuses.items():
                connection.execute(
                    "UPDATE engineering_simulation_campaign_runs SET status = %s WHERE campaign_id = %s AND job_id = %s",
                    (status, campaign_id, job_id),
                )
            connection.execute(
                "UPDATE engineering_simulation_campaigns SET status = %s, "
                "completed_at = CASE WHEN %s THEN now() ELSE NULL END "
                "WHERE project_id = %s AND campaign_id = %s",
                (campaign_status, complete, project_id, campaign_id),
            )
            connection.commit()
        return get_campaign_record(project_id, campaign_id)
    finally:
        reset_project(token)
