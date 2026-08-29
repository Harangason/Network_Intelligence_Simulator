"""Struktur, Parser und Completion-Entscheidung fuer Engineering-Workloads."""

from __future__ import annotations

import re
from typing import Any

try:
    from backend.agent_core.errors import AgentCoreValidationError
    from backend.agent_core.validation import CompletionValidator
except ModuleNotFoundError:  # Tests execute with backend as the import root.
    from agent_core.errors import AgentCoreValidationError
    from agent_core.validation import CompletionValidator

from ..models import EngineeringValidationError

WORKLOAD_STATUSES = (
    "RECEIVED",
    "PLANNING",
    "IN_PROGRESS",
    "VALIDATING",
    "INCOMPLETE",
    "READY_FOR_REVIEW",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "NEEDS_REVIEW",
    "PAUSED",
    "CANCELED",
)

WORKLOAD_TYPES = (
    "SIGNAL_GENERATION",
    "NODE_GENERATION",
    "ECU_GENERATION",
    "INTERFACE_GENERATION",
    "MESSAGE_GENERATION",
    "ROUTING_GENERATION",
    "NETWORK_GENERATION",
    "PARAMETER_GENERATION",
    "VALIDATION_RULE_GENERATION",
    "SCENARIO_GENERATION",
    "FAULT_GENERATION",
    "TEST_CASE_GENERATION",
    "TRACE_FINDING_GENERATION",
    "DOCUMENTATION",
    "TRACE_ANALYSIS",
    "NETWORK_ANALYSIS",
    "BUS_LOAD_ANALYSIS",
)

WORKLOAD_OBJECT_TYPES: dict[str, str] = {
    "SIGNAL_GENERATION": "Signal",
    "NODE_GENERATION": "HardwareNode",
    "ECU_GENERATION": "HardwareNode",
    "INTERFACE_GENERATION": "Interface",
    "MESSAGE_GENERATION": "Message",
    "ROUTING_GENERATION": "RoutingEntry",
    "NETWORK_GENERATION": "Network",
    "PARAMETER_GENERATION": "Parameter",
    "VALIDATION_RULE_GENERATION": "ValidationRule",
    "SCENARIO_GENERATION": "SimulationScenario",
    "FAULT_GENERATION": "FaultScenario",
    "TEST_CASE_GENERATION": "TestCase",
    "TRACE_FINDING_GENERATION": "TraceFinding",
    "DOCUMENTATION": "Documentation",
    "TRACE_ANALYSIS": "TraceAnalysis",
    "NETWORK_ANALYSIS": "NetworkAnalysis",
    "BUS_LOAD_ANALYSIS": "BusLoadAnalysis",
}

_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("BUS_LOAD_ANALYSIS", re.compile(r"\b(bus\s*load|buslast|auslastung)\b", re.I)),
    ("TRACE_ANALYSIS", re.compile(r"\b(trace|traces)\b.*\b(analy|auswert)", re.I)),
    ("NETWORK_ANALYSIS", re.compile(r"\bnetzwerk\b.*\b(analy|auswert)", re.I)),
    ("FAULT_GENERATION", re.compile(r"\b(fault|fehler)\s*(szenar|scenario)", re.I)),
    ("SCENARIO_GENERATION", re.compile(r"\b(szenar|scenario)", re.I)),
    ("ROUTING_GENERATION", re.compile(r"\b(routing|routen?|routing entries)\b", re.I)),
    ("INTERFACE_GENERATION", re.compile(r"\b(interfaces?|schnittstellen?)\b", re.I)),
    ("MESSAGE_GENERATION", re.compile(r"\b(messages?|nachrichten?)\b", re.I)),
    ("SIGNAL_GENERATION", re.compile(r"\bsignale?\b", re.I)),
    ("ECU_GENERATION", re.compile(r"\becus?\b", re.I)),
    ("NODE_GENERATION", re.compile(r"\b(knoten|nodes?)\b", re.I)),
    ("PARAMETER_GENERATION", re.compile(r"\bparameter\b", re.I)),
    ("TEST_CASE_GENERATION", re.compile(r"\b(testf[aä]lle?|test cases?)\b", re.I)),
    ("DOCUMENTATION", re.compile(r"\b(dokumentation|documentation)\b", re.I)),
)

_CATEGORY_ALIASES = {
    "temperature": "thermal",
    "temperatur": "thermal",
    "thermal": "thermal",
    "motion": "motion",
    "bewegung": "motion",
    "dynamik": "motion",
    "golden": "golden",
    "fault": "fault",
    "fehler": "fault",
    "stress": "stress",
}


def _normalized_category(value: Any) -> str:
    text = str(value or "general").strip().lower()
    key = re.sub(r"[^a-z0-9äöüß_-]+", "-", text).strip("-") or "general"
    return _CATEGORY_ALIASES.get(key, key)


def _workload_type(prompt: str, explicit: Any) -> str:
    if explicit:
        value = str(explicit).strip().upper()
        if value not in WORKLOAD_TYPES:
            raise EngineeringValidationError(f"Unbekannter Workload-Typ: {value!r}.")
        return value
    for workload_type, pattern in _TYPE_PATTERNS:
        if pattern.search(prompt):
            return workload_type
    raise EngineeringValidationError(
        "Der Auftrag enthaelt keinen unterstuetzten Workload-Typ. "
        "workload_type muss explizit angegeben werden."
    )


def _explicit_total(prompt: str) -> int | None:
    patterns = (
        r"\b(?:insgesamt|gesamt|total)\s*[:=]?\s*(\d{1,5})\b",
        r"\berzeuge\s+(\d{1,5})\s+",
        r"\b(?:generate|create)\s+(\d{1,5})\s+",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.I)
        if match:
            return int(match.group(1))
    return None


def _prompt_packages(prompt: str) -> list[dict[str, Any]]:
    categories = "temperatur|temperature|thermal|motion|bewegung|dynamik|golden|fault|fehler|stress"
    patterns = (
        rf"(\d{{1,5}})\s*(?:weitere\s+)?(?:signale?|messages?|nachrichten?|szenarien?|scenarios?)?\s*f(?:u|ue|ü)r\s+(?:die\s+|den\s+|das\s+)?({categories})\b",
        rf"(\d{{1,5}})\s+(?:signale?|messages?|nachrichten?|szenarien?|scenarios?)?\s*({categories})\b",
        rf"({categories})\s*[:=]\s*(\d{{1,5}})\b",
    )
    found: dict[str, int] = {}
    for pattern_index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, prompt, re.I):
            if pattern_index == 2:
                category, count = match.group(1), int(match.group(2))
            else:
                count, category = int(match.group(1)), match.group(2)
            key = _normalized_category(category)
            found[key] = max(found.get(key, 0), count)
    return [
        {"category": category, "requested_count": count}
        for category, count in found.items()
    ]


def _payload_packages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_packages = payload.get("work_packages") or payload.get("targets") or []
    if not isinstance(raw_packages, list):
        raise EngineeringValidationError("work_packages muss eine Liste sein.")
    packages: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_packages):
        if not isinstance(raw, dict):
            raise EngineeringValidationError(f"Work Package {index + 1} ist kein Objekt.")
        count = raw.get("requested_count", raw.get("target", raw.get("count")))
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise EngineeringValidationError(f"Work Package {index + 1} besitzt keine positive Zielmenge.")
        packages.append(
            {
                "category": _normalized_category(raw.get("category") or raw.get("name") or f"package-{index + 1}"),
                "requested_count": count,
                "configuration": dict(raw.get("configuration") or {}),
            }
        )
    return packages


def parse_workload_request(prompt: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse a user outcome into measurable packages without declaring completion."""
    payload = dict(payload or {})
    prompt = str(prompt or payload.get("prompt") or "").strip()
    if not prompt:
        raise EngineeringValidationError("prompt ist fuer einen Workload erforderlich.")
    workload_type = _workload_type(prompt, payload.get("workload_type"))
    target_object = str(payload.get("target_object") or WORKLOAD_OBJECT_TYPES[workload_type])
    packages = _payload_packages(payload) or _prompt_packages(prompt)
    requested_total = payload.get("requested_total")
    if requested_total is None:
        requested_total = _explicit_total(prompt)
    if requested_total is None and packages:
        requested_total = sum(item["requested_count"] for item in packages)
    if not isinstance(requested_total, int) or isinstance(requested_total, bool) or requested_total <= 0:
        raise EngineeringValidationError("Eine positive Gesamtzielmenge konnte nicht ermittelt werden.")
    if not packages:
        packages = [{"category": "general", "requested_count": requested_total, "configuration": {}}]
    package_total = sum(item["requested_count"] for item in packages)
    if package_total != requested_total:
        raise EngineeringValidationError(
            f"WORKLOAD_CONFIGURATION_ERROR: Teilziele ergeben {package_total}, Gesamtziel ist {requested_total}."
        )

    max_attempts = payload.get("max_generation_attempts", 3)
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= 10:
        raise EngineeringValidationError("max_generation_attempts muss zwischen 1 und 10 liegen.")
    for index, package in enumerate(packages, start=1):
        package["package_code"] = str(package.get("package_code") or f"WP-{index:02d}")
        package["target_object"] = target_object
        package["max_generation_attempts"] = max_attempts

    completion_criteria = payload.get("completion_criteria") or [
        {"metric": "total_valid", "operator": "eq", "value": requested_total},
        {"metric": "duplicate_count", "operator": "eq", "value": 0},
        {"metric": "invalid_count", "operator": "eq", "value": 0},
        {"metric": "all_required_fields_valid", "operator": "eq", "value": True},
        {"metric": "all_objects_persisted", "operator": "eq", "value": True},
    ]
    return {
        "workload_type": workload_type,
        "title": str(payload.get("title") or f"Generate {requested_total} {target_object} objects"),
        "description": str(payload.get("description") or prompt),
        "prompt": prompt,
        "domain": payload.get("domain"),
        "target_object": target_object,
        "requested_total": requested_total,
        "requested_count": requested_total,
        "work_packages": packages,
        "constraints": list(payload.get("constraints") or []),
        "dependencies": list(payload.get("dependencies") or []),
        "validation_rules": list(payload.get("validation_rules") or []),
        "completion_criteria": completion_criteria,
        "max_generation_attempts": max_attempts,
        "parent_workload_id": payload.get("parent_workload_id"),
        "created_by": payload.get("created_by") or payload.get("actor"),
        "agent": payload.get("agent"),
        "model": payload.get("model"),
    }


def evaluate_workload_completion(
    workload: dict[str, Any],
    packages: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    dependencies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate completion exclusively from persisted structured state."""
    try:
        return CompletionValidator().evaluate(workload, packages, objects, dependencies or [])
    except AgentCoreValidationError as error:
        raise EngineeringValidationError(str(error)) from error
