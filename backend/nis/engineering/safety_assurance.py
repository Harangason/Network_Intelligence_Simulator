"""Revision-bound technical safety evidence. No normative or human approval.

The E2E calculator remains the authority for delivery/acceptance timing. This
module adds explicitly configured safety criteria and causal reaction evidence.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
from hashlib import sha256
import json
from math import isfinite

from backend.nis.domain.vocabulary import EngineeringValidationError
from backend.nis.simulation.e2e_assurance import build_e2e_transactions

SCHEMA = "nis.safety-evidence.v1"
RULE_VERSION = "1.0"
STANDARD_SOURCES = {
    "ISO 26262": "https://www.iso.org/standard/68383.html",
    "UN R155": "https://unece.org/transport/documents/2021/03/standards/un-regulation-no-155-cyber-security-and-cyber-security",
    "UN R156": "https://unece.org/transport/documents/2021/03/standards/un-regulation-no-156-software-update-and-software-update",
}
FAULT_TYPES = {"LOSS", "REPETITION", "CORRUPTION", "WRONG_SEQUENCE", "TIMEOUT", "DELAY", "STALE_DATA", "LINK_DOWN", "QUEUE_OVERFLOW", "WRONG_SENDER"}
PROTECTIONS = {"CRC", "SEQUENCE_COUNTER", "ALIVE_COUNTER", "DATA_ID", "TIMEOUT_MONITOR", "FRESHNESS", "SOURCE_AUTHENTICATION"}


def digest(value):
    # Browser JSON preserves number values, but serializes 2.0 as 2. Normalize
    # integral floats at the exchange boundary, without changing the evidence.
    def canonical(item):
        if isinstance(item, dict): return {key: canonical(child) for key, child in item.items()}
        if isinstance(item, list): return [canonical(child) for child in item]
        if type(item) is float and isfinite(item) and item.is_integer(): return int(item)
        return item
    return sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise EngineeringValidationError("Safety-Konfiguration enthält fehlende oder unbekannte Felder.")


def _text(value, label, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise EngineeringValidationError(f"{label}: begrenzter, nicht leerer Text erforderlich.")
    return value.strip()


def _number(value):
    return float(value) if type(value) in (int, float) and isfinite(value) and value >= 0 else None


def validate_requirement(config):
    _fields(config, {"profile", "hazard_ref", "safety_goal_ref", "integrity", "route_ids", "criteria", "eip"}, {"profile", "hazard_ref", "safety_goal_ref", "route_ids", "criteria"})
    profile = config["profile"]
    _fields(profile, {"standard", "edition", "domain", "applicability", "reason", "clause_refs", "work_product_refs"}, {"standard", "edition", "domain", "applicability", "reason"})
    for field in ("standard", "edition", "domain", "reason"):
        _text(profile[field], field)
    if not isinstance(profile["applicability"], str) or profile["applicability"] not in {"APPLICABLE", "NOT_APPLICABLE", "UNRESOLVED"}:
        raise EngineeringValidationError("Explizite Anwendbarkeit erforderlich.")
    for field in ("clause_refs", "work_product_refs"):
        values = profile.get(field, [])
        if not isinstance(values, list) or len(values) > 32:
            raise EngineeringValidationError(f"{field}: maximal 32 Referenzen.")
        for value in values: _text(value, field)
    for field in ("hazard_ref", "safety_goal_ref"):
        _text(config[field], field)
    if "integrity" in config:
        _fields(config["integrity"], {"model", "level", "decision_ref"}, {"model", "level", "decision_ref"})
        for field, value in config["integrity"].items(): _text(value, field)
    routes = config["route_ids"]
    if not isinstance(routes, list) or not 1 <= len(routes) <= 32 or len(set(map(str, routes))) != len(routes):
        raise EngineeringValidationError("1–32 eindeutige Routen erforderlich.")
    for value in routes: _text(value, "route_id", 200)
    criteria = config["criteria"]
    _fields(criteria, {"deadline_ms", "freshness_ms", "required_protections", "fault_cases"})
    for field in ("deadline_ms", "freshness_ms"):
        if field in criteria and _number(criteria[field]) is None:
            raise EngineeringValidationError(f"{field}: endliche, nicht negative Zahl erforderlich.")
    protections = criteria.get("required_protections", [])
    if not isinstance(protections, list) or any(not isinstance(value, str) or value not in PROTECTIONS for value in protections) or len(set(protections)) != len(protections):
        raise EngineeringValidationError("Unbekannter oder doppelter Schutzmechanismus.")
    faults = criteria.get("fault_cases", [])
    if not isinstance(faults, list) or len(faults) > 32:
        raise EngineeringValidationError("Maximal 32 Fehlerfälle.")
    ids = set()
    for fault in faults:
        _fields(fault, {"id", "type", "ftti_ms", "detection_ms", "safe_state", "receiver_id"}, {"id", "type", "ftti_ms", "detection_ms", "safe_state", "receiver_id"})
        key = _text(fault["id"], "Fehlerfall", 200)
        if key in ids or not isinstance(fault["type"], str) or fault["type"] not in FAULT_TYPES:
            raise EngineeringValidationError("Unbekannter Fehlerfall oder doppelte Fall-ID.")
        ids.add(key); _text(fault["safe_state"], "safe_state")
        _text(fault["receiver_id"], "receiver_id", 200)
        if any(_number(fault[field]) is None for field in ("ftti_ms", "detection_ms")):
            raise EngineeringValidationError("FTTI und Erkennungsfrist müssen explizite endliche Grenzen sein.")
    if "eip" in config:
        eip = config["eip"]
        _fields(eip, {"project_id", "requirement_ref", "source_revisions"}, {"project_id", "requirement_ref", "source_revisions"})
        _text(eip["project_id"], "EIP-Projekt", 200); _text(eip["requirement_ref"], "EIP-Anforderung", 200)
        revisions = eip["source_revisions"]
        if not isinstance(revisions, dict) or not 1 <= len(revisions) <= 20 or eip["requirement_ref"] not in revisions:
            raise EngineeringValidationError("Originale EIP-Anforderungsrevision und Quellenrevisionen erforderlich.")
        for ref, revision in revisions.items():
            _text(ref, "EIP-Quelle", 200)
            if type(revision) is not int or revision < 1:
                raise EngineeringValidationError("Positive originale EIP-Revision erforderlich.")
    return deepcopy(config)


def validate_bindings(data):
    """Every local reference resolves in the active canonical project."""
    from backend.nis.infrastructure.persistence.repository import get_object
    from backend.nis.engineering.routing.repository import get_route
    function = get_object("Function", str(data.get("function_id") or ""))
    endpoint_ids = set()
    for route_id in data["configuration"]["route_ids"]:
        route = get_route(route_id)
        endpoints = [route.get("source") or {}, *(route.get("destinations") or [])]
        endpoint_ids.update(str(endpoint.get("node_id")) for endpoint in endpoints)
        if not any(str(endpoint.get("node_id")) == str(function["hardware_node_id"]) for endpoint in endpoints):
            raise EngineeringValidationError("Safety-Funktion gehört zu keinem Endpunkt der zugeordneten Route.")
    for case in data["configuration"]["criteria"].get("fault_cases", []):
        get_object("HardwareNode", case["receiver_id"])
        if case["receiver_id"] not in endpoint_ids:
            raise EngineeringValidationError("Fehlerfall-Empfänger gehört zu keinem Endpunkt des Sicherheitsumfangs.")
    return function


def _status(values):
    return "FAIL" if "FAIL" in values else "PASS" if values and all(value == "PASS" for value in values) else "NOT_EVALUATED"


def active_requirements(rows):
    return [row for row in rows if row.get("lifecycle_state") not in {"deprecated", "superseded"}]


def assess_requirements(requirements, events, routes, *, time_basis="UNKNOWN"):
    """Only explicit emitted evidence counts; physical SAFE_STATE labels do not.

    Fault events need requirement/case/occurrence identity, receiver identity,
    original causal IDs and one declared clock basis. Missing cases stay open.
    """
    results = []
    event_counts = Counter(str(event.get("event_id")) for event in events if event.get("event_id"))
    for requirement in active_requirements(requirements):
        config = validate_requirement(requirement["configuration"])
        criteria, profile = config["criteria"], config["profile"]
        checks = []; evidence = set(); gaps = []
        aliases = {ref: [key for key, route in routes.items() if key == ref or route.get("canonical_route_id") == ref or ref in route.get("routing_entry_ids", [])] for ref in config["route_ids"]}
        route_map = {key: {**routes[key], **({"deadline_ms": criteria["deadline_ms"], "max_e2e_latency_ms": criteria["deadline_ms"]} if "deadline_ms" in criteria else {}),
            **({"max_data_age_ms": criteria["freshness_ms"]} if "freshness_ms" in criteria else {})} for keys in aliases.values() for key in keys}
        route_events = [event for event in events if str(event.get("end_to_end_route_id") or event.get("route_id") or "") in route_map
            and event.get("event_type") not in {"SAFETY_FAULT", "SAFETY_DETECTION", "SAFETY_REACTION"}]
        accepted_events = {}
        for event in route_events:
            if str(event.get("receiver_status") or "").upper() == "ACCEPTED" or event.get("event_type") == "RECEIVER_ACCEPTANCE":
                accepted_events[str(event.get("transaction_id") or event.get("end_to_end_event_id"))] = event
        transactions = build_e2e_transactions(route_events, route_map)
        for route_id in config["route_ids"]:
            selected = [item for item in transactions if item["route_id"] in aliases[route_id]]
            statuses = []
            if not aliases[route_id] or any(not any(item["route_id"] == key for item in selected) for key in aliases[route_id]):
                statuses.append("NOT_EVALUATED")
            for item in selected:
                values = [item["requirement_status"]]
                if time_basis == "UNKNOWN" or not item["evidence_event_ids"] or any(event_counts[key] != 1 for key in item["evidence_event_ids"]): values.append("NOT_EVALUATED")
                evidence.update(item["evidence_event_ids"])
                if criteria.get("required_protections"):
                    acceptance = accepted_events.get(item["transaction_id"], {})
                    proofs = acceptance.get("protection_checks") or {}
                    for protection in criteria["required_protections"]:
                        value = proofs.get(protection) if isinstance(proofs, dict) else None
                        values.append(value if isinstance(value, str) and value in {"PASS", "FAIL"} else "NOT_EVALUATED")
                statuses.append(_status(values))
            checks.append({"id": route_id, "kind": "COMMUNICATION", "status": _status(statuses), "sample_count": len(selected),
                "transaction_ids": [item["transaction_id"] for item in selected],
                "deadline_ms": criteria.get("deadline_ms"), "freshness_ms": criteria.get("freshness_ms"),
                "observed_max_latency_ms": max((item["e2e_latency_ms"] for item in selected if item["e2e_latency_ms"] is not None), default=None),
                "observed_max_data_age_ms": max((item["data_age_at_accept_ms"] for item in selected if item["data_age_at_accept_ms"] is not None), default=None)})
        for case in criteria.get("fault_cases", []):
            relevant = [event for event in events if event.get("safety_requirement_id") == str(requirement["id"])
                and event.get("fault_case_id") == case["id"]]
            faults = [event for event in relevant if event.get("event_type") == "SAFETY_FAULT" and event.get("fault_type") == case["type"]]
            outcomes = []; observations = []
            occurrence_counts = Counter(str(event.get("fault_occurrence_id")) for event in faults)
            for fault in faults:
                occurrence = fault.get("fault_occurrence_id"); fault_id = fault.get("event_id")
                correlated = [event for event in relevant if occurrence and event.get("fault_occurrence_id") == occurrence
                    and event.get("caused_by_event_id") == fault_id and event.get("receiver_id") == fault.get("receiver_id")]
                detections = [event for event in correlated if event.get("event_type") == "SAFETY_DETECTION"]
                reactions = [event for event in correlated if event.get("event_type") == "SAFETY_REACTION" and event.get("physical_state_observed") is True]
                detection = detections[0] if len(detections) == 1 else None
                reaction = reactions[0] if len(reactions) == 1 else None
                proof = [fault, detection, reaction]
                valid = all(proof) and occurrence_counts[str(occurrence)] == 1 and len({event.get("event_id") for event in proof}) == 3 and all(_number(event.get("time_s")) is not None and event.get("event_id") and event_counts[str(event["event_id"])] == 1 and event.get("time_basis") == time_basis for event in proof)
                if not valid or time_basis == "UNKNOWN" or fault.get("receiver_id") != case["receiver_id"]:
                    outcomes.append("NOT_EVALUATED"); continue
                evidence.update(event["event_id"] for event in proof)
                detected = round((detection["time_s"] - fault["time_s"]) * 1000, 6)
                reacted = round((reaction["time_s"] - fault["time_s"]) * 1000, 6)
                outcomes.append("PASS" if 0 <= detected <= reacted and detected <= case["detection_ms"] and reacted <= case["ftti_ms"] and reaction.get("observed_state") == case["safe_state"] else "FAIL")
                observations.append({"fault_event_id": fault_id, "detection_event_id": detection["event_id"], "reaction_event_id": reaction["event_id"],
                    "receiver_id": fault["receiver_id"], "detection_ms": detected, "reaction_ms": reacted, "observed_state": reaction.get("observed_state"), "status": outcomes[-1]})
            checks.append({"id": case["id"], "kind": "FAULT_REACTION", "status": _status(outcomes), "sample_count": len(faults),
                "detection_limit_ms": case["detection_ms"], "ftti_ms": case["ftti_ms"], "safe_state": case["safe_state"], "observations": observations})
        if not criteria.get("fault_cases"): gaps.append("fault_reaction_scope_not_defined")
        if not ("deadline_ms" in criteria or "freshness_ms" in criteria): gaps.append("communication_timing_criteria_missing")
        if profile["applicability"] == "UNRESOLVED": gaps.append("applicability_unresolved")
        if not profile.get("clause_refs"): gaps.append("normative_clause_scope_missing")
        if not profile.get("work_product_refs"): gaps.append("normative_work_products_missing")
        if "integrity" not in config: gaps.append("integrity_decision_missing")
        if "eip" not in config: gaps.append("eip_chain_missing")
        gaps.extend(f"{check['id']}:evidence_missing" for check in checks if check["status"] == "NOT_EVALUATED")
        results.append({"id": str(requirement["id"]), "name": requirement["name"], "revision": requirement["version"], "function_id": str(requirement["function_id"]),
            "configuration": config, "technical_status": _status([check["status"] for check in checks]), "checks": checks,
            "evidence_event_ids": sorted(evidence), "gaps": gaps, "normative_status": "NOT_EVALUATED", "review_status": "REVIEW_REQUIRED"})
    return {"schema": SCHEMA, "rule_version": RULE_VERSION, "requirements": results, "technical_status": _status([row["technical_status"] for row in results]),
        "normative_status": "NOT_EVALUATED", "release_approved": False, "time_basis": time_basis,
        "limitations": ["Project-defined technical criteria only; no ASIL assignment or normative conformity.", "Physical safe-state reaction requires explicit causal measurement evidence.", "Independent human approval and complete lifecycle/regulatory evidence remain separate."]}


def export_snapshot(project_id, snapshot, current_requirements):
    """Export frozen server-produced evidence, never client supplied PASS values."""
    config = (snapshot or {}).get("configuration") or {}
    frozen = (config.get("engineering_model") or {}).get("safety_requirements", [])
    report = ((snapshot or {}).get("result") or {}).get("runtime_metrics", {}).get("safety_assurance")
    current_vector = {str(row["id"]): row["version"] for row in active_requirements(current_requirements)}
    frozen_vector = {str(row["id"]): row["version"] for row in active_requirements(frozen)}
    completed = str((snapshot or {}).get("status", "")).upper() in {"COMPLETED", "COMPLETE"}
    fresh = bool(snapshot) and not snapshot.get("is_outdated", True) and current_vector == frozen_vector
    payload = {"schema": SCHEMA, "rule_version": RULE_VERSION, "project_id": project_id,
        "snapshot_id": str((snapshot or {}).get("id") or ""), "job_id": (snapshot or {}).get("job_id"),
        "source_versions": (snapshot or {}).get("source_versions") or {}, "requirement_revisions": frozen_vector,
        "execution_status": "COMPLETED" if completed else "NOT_COMPLETED", "freshness": "CURRENT" if fresh else "OUTDATED",
        "assessment": deepcopy(report) if isinstance(report, dict) and completed else assess_requirements([], [], {}),
        "release_approved": False}
    if not report: payload["assessment"]["limitations"].append("No frozen safety report; rerun with configured requirements.")
    return {"payload": payload, "sha256": digest(payload)}
