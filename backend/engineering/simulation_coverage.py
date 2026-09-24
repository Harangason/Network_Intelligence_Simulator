"""Shared, ID-based simulation scope, transport coverage and result assessment.

No storage or inference is performed here. Missing routes never silently narrow
the requested scope, and an executed job is not itself evidence of conformance.
"""
from __future__ import annotations

from typing import Any

INACTIVE = {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}
RETIRED_TRANSPORTS = {"REJECTED", "SUPERSEDED", "DEPRECATED"}


def _ids(values: Any) -> set[str]:
    return {str(value) for value in values if value is not None and str(value)} if isinstance(values, list) else set()


def active_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if str(row.get("lifecycle_state") or "").upper() not in INACTIVE
            and str(row.get("status") or "").upper() not in INACTIVE]


def _unused_function_outputs(messages: list[dict], signal_messages: dict[str, str],
                             transports: list[dict]) -> set[str]:
    # Invalid or outdated paths still express current transport intent. Only
    # explicitly discarded historical paths can cease to block this exemption.
    linked = set()
    for row in transports:
        if str(row.get("status") or "").upper() in RETIRED_TRANSPORTS:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        linked.update(_ids(payload.get("message_ids")))
        if payload.get("message_id"):
            linked.add(str(payload["message_id"]))
        signal_ids = _ids(payload.get("signal_ids"))
        if payload.get("signal_id"):
            signal_ids.add(str(payload["signal_id"]))
        linked.update(signal_messages[key] for key in signal_ids if key in signal_messages)
    excluded = set()
    for message in messages:
        if not message.get("id"):
            continue
        config = message.get("configuration")
        if not isinstance(config, dict):
            continue
        contract, routing = config.get("communication_contract"), config.get("routing")
        transport = config.get("transport_unit", {})
        if not all(isinstance(value, dict) for value in (contract, routing, transport)):
            continue
        provenance = transport.get("provenance", {})
        if not isinstance(provenance, dict):
            continue
        role, generator = contract.get("role"), provenance.get("generator")
        if any(value is not None and not isinstance(value, str) for value in (role, generator)):
            continue
        local_role = role in {"MEASUREMENT", "FEEDBACK", "COMMAND"}
        local_generator = generator == "wizard-local-actuator-command"
        internal_state = (role == "INTERNAL_STATE" and contract.get("scope") in {"INTERNAL", "FUNCTION_OUTPUT"}
                          and not contract.get("consumer_refs") and not transport.get("consumer_refs"))
        unused_output = contract.get("scope") == "FUNCTION_OUTPUT" and not local_role and not local_generator
        if (str(message.get("id")) not in linked
                and routing.get("enabled") is False
                and (internal_state or unused_output)):
            excluded.add(str(message["id"]))
    return excluded


def simulation_coverage(messages: list[dict], signals: list[dict], transports: list[dict],
                        scope: dict | None = None, *, declared_transports: list[dict] | None = None) -> dict[str, Any]:
    all_signal_messages = {str(row["id"]): str(row.get("message_id") or "") for row in signals if row.get("id")}
    messages, signals = active_rows(messages), active_rows(signals)
    message_ids = {str(row["id"]) for row in messages if row.get("id")}
    signal_ids = {str(row["id"]) for row in signals if row.get("id")}
    signal_messages = {str(row["id"]): str(row.get("message_id") or "") for row in signals if row.get("id")}
    scope = scope if isinstance(scope, dict) else {}
    selected = not scope.get("include_all") and str(scope.get("mode") or "ALL").upper() != "ALL"
    errors: list[str] = []
    required_messages, required_signals = set(message_ids), set(signal_ids)
    transport_exclusions = []
    if selected:
        requested_messages, requested_signals = _ids(scope.get("message_ids")), _ids(scope.get("signal_ids"))
        if not requested_messages and not requested_signals:
            errors.append("Der ausgewählte Simulationsumfang ist leer.")
        if requested_messages - message_ids or requested_signals - signal_ids:
            errors.append("Der ausgewählte Simulationsumfang enthält unbekannte Objekt-IDs.")
        required_messages = requested_messages & message_ids
        required_signals = requested_signals & signal_ids
        required_signals.update(key for key, parent in signal_messages.items() if parent in required_messages)
        required_messages.update(signal_messages[key] for key in required_signals if signal_messages[key] in message_ids)
    else:
        # Only the complete, explicitly disabled function output has no external
        # transport obligation. Signal switches never repack a physical frame.
        excluded = _unused_function_outputs(messages, all_signal_messages, [*transports, *(declared_transports or [])])
        message_names = {str(message["id"]): str(message.get("name") or message["id"]) for message in messages if message.get("id")}
        excluded_children = {message_id: set() for message_id in excluded}
        for key, parent in signal_messages.items():
            if parent in excluded_children:
                excluded_children[parent].add(key)
        for message_id in sorted(excluded):
            excluded_signals = excluded_children[message_id]
            required_messages.discard(message_id)
            required_signals.difference_update(excluded_signals)
            internal_state = next((message for message in messages if str(message.get("id")) == message_id), None)
            contract = ((internal_state or {}).get("configuration") or {}).get("communication_contract") or {}
            is_internal = contract.get("role") == "INTERNAL_STATE" and contract.get("scope") in {"INTERNAL", "FUNCTION_OUTPUT"}
            transport_exclusions.append({"message_id": message_id, "message_name": message_names[message_id],
                "signal_ids": sorted(excluded_signals),
                "reason_code": "INTERNAL_STATE_NOT_ROUTED" if is_internal else "EXPLICIT_FUNCTION_OUTPUT_NOT_ROUTED",
                "reason": ("Der Controllerstatus bleibt ohne bestätigten Empfänger intern. " if is_internal else
                           "Der vollständige Funktionsausgang ist ausdrücklich nicht geroutet und besitzt keine aktuelle Transportabsicht. ")
                          + "Vom Transportscope ausgenommen; keine funktionale Beobachtung oder Timing-Freigabe nachgewiesen."})

    covered_messages, covered_signals = set(), set()
    for row in active_rows(transports):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        linked_messages = _ids(payload.get("message_ids"))
        if payload.get("message_id"):
            linked_messages.add(str(payload["message_id"]))
        linked_signals = _ids(payload.get("signal_ids"))
        covered_signals.update(linked_signals if linked_signals else
                               {key for key, parent in signal_messages.items() if parent in linked_messages})
        covered_messages.update(linked_messages)
        covered_messages.update(signal_messages[key] for key in linked_signals if key in signal_messages)
    covered_messages &= required_messages
    covered_signals &= required_signals
    missing_messages, missing_signals = required_messages - covered_messages, required_signals - covered_signals
    return {
        "version": 1, "scope_mode": "SELECTED" if selected else "ALL",
        "complete": not errors and not missing_messages and not missing_signals,
        "errors": errors,
        "total_messages": len(message_ids), "total_signals": len(signal_ids),
        "required_messages": len(required_messages), "required_signals": len(required_signals),
        "covered_messages": len(covered_messages), "covered_signals": len(covered_signals),
        "excluded_messages": len(message_ids - required_messages), "excluded_signals": len(signal_ids - required_signals),
        "excluded_message_ids": sorted(message_ids - required_messages), "excluded_signal_ids": sorted(signal_ids - required_signals),
        "transport_exclusions": transport_exclusions,
        "message_coverage_percent": round(100 * len(covered_messages) / len(required_messages), 2) if required_messages else 100.0,
        "signal_coverage_percent": round(100 * len(covered_signals) / len(required_signals), 2) if required_signals else 100.0,
        "required_message_ids": sorted(required_messages), "required_signal_ids": sorted(required_signals),
        "missing_message_ids": sorted(missing_messages), "missing_signal_ids": sorted(missing_signals),
    }


def assess_simulation(configuration: dict, result: dict | None) -> dict[str, Any]:
    result = result or {}
    model = configuration.get("engineering_model") or {}
    scenario = configuration.get("scenario") or {}
    scope = scenario.get("simulation_scope") or configuration.get("simulation_scope") or {}
    coverage = configuration.get("scope_coverage") or simulation_coverage(
        model.get("messages") or [], model.get("signals") or [], configuration.get("communications") or [], scope,
        declared_transports=model.get("routes") or [])
    series = (result.get("model_simulation") or {}).get("signals")
    observed_ids = {str(row.get("signal_id") or row.get("id")) for row in (series or [])
                    if isinstance(row, dict) and (row.get("signal_id") or row.get("id"))}
    # The model engine supplies the complete per-signal summary, not a UI page.
    observed_missing = set(coverage["required_signal_ids"]) - observed_ids
    runtime = result.get("runtime_metrics") or {}
    routes = runtime.get("routes") or []
    failed = sum(row.get("status") == "FAIL" for row in routes)
    unevaluated = sum(row.get("status") != "PASS" and row.get("status") != "FAIL" for row in routes)
    known_expected_routes = {str(row.get("routing_entry_id") or row.get("canonical_route_id") or row.get("id"))
                             for row in configuration.get("communications") or []}
    observed_routes = {str(row.get("canonical_route_id") or row.get("routing_entry_id") or row.get("route_id"))
                       for row in routes}
    # Legacy metric IDs can be resolved only through this frozen config.
    by_runtime_id = {str(row.get("id")): str(row.get("routing_entry_id") or row.get("canonical_route_id") or row.get("id"))
                     for row in configuration.get("communications") or []}
    observed_routes.update(by_runtime_id[str(row.get("route_id"))] for row in routes if str(row.get("route_id")) in by_runtime_id)
    missing_routes = known_expected_routes - observed_routes
    expected_networks = {str(row.get("id")) for row in configuration.get("networks") or [] if row.get("id")}
    if not scope.get("include_all") and str(scope.get("mode") or "ALL").upper() != "ALL":
        # The frozen inventory retains networks outside an explicit selection.
        # Require evidence for every segment of the selected transports, not
        # for independent networks intentionally excluded from this run.
        expected_networks = {
            str(endpoint["network_id"])
            for communication in configuration.get("communications") or []
            for endpoint in [communication, *(communication.get("segments") or [])]
            if endpoint.get("network_id")
        }
    observed_networks = {str(row.get("network_id")) for row in runtime.get("networks") or []}
    missing_networks = expected_networks - observed_networks
    has_evidence = bool(runtime.get("available") and routes)
    incomplete = (not coverage["complete"] or bool(observed_missing) or bool(missing_routes)
                  or bool(missing_networks) or not has_evidence)
    status = "ERROR" if failed else ("WARNING" if incomplete or unevaluated else "COMPLETE")
    return {
        "version": 1, "status": status, "execution_completed": True,
        "release": configuration.get("release"),
        "conformance": "FAIL" if failed else ("NOT_EVALUATED" if incomplete or unevaluated else "PASS"),
        "scope_coverage": coverage, "observed_signal_count": len(observed_ids & set(coverage["required_signal_ids"])),
        "missing_observed_signal_ids": sorted(observed_missing), "missing_observed_route_ids": sorted(missing_routes),
        "missing_observed_network_ids": sorted(missing_networks), "failed_route_count": failed,
        "unevaluated_route_count": unevaluated, "evaluated_route_count": len(routes) - unevaluated,
        "expected_route_count": len(known_expected_routes), "scenario_mode": scenario.get("mode") or "NORMAL",
    }
