"""Deterministic orchestrator for requirement expansion.

The engine combines small pure-Python helper modules into a single structured
proposal object expected by the engineering workload handler.
"""

from __future__ import annotations

from typing import Any

from backend.nis.engineering.requirements.generation_rule_manager import resolve_generation_policy
from backend.nis.engineering.requirement_expansion_modules.analysis import derive_ambiguity
from backend.nis.engineering.requirement_expansion_modules.analysis import derive_assumptions
from backend.nis.engineering.requirement_expansion_modules.analysis import derive_completion_report
from backend.nis.engineering.requirement_expansion_modules.analysis import derive_findings
from backend.nis.engineering.requirement_expansion_modules.analysis import derive_open_decisions
from backend.nis.engineering.requirement_expansion_modules.constants import ENGINE_VERSION
from backend.nis.engineering.requirement_expansion_modules.constants import WORKFLOW_STATUSES
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_capacity
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_communications
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_coordinate_system
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_data_objects
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_functions
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_hardware
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_messages
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_parameters
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_routing
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_sensors
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_signals
from backend.nis.engineering.requirement_expansion_modules.derivations import derive_status_models
from backend.nis.engineering.requirement_expansion_modules.resolution import choose_domain
from backend.nis.engineering.requirement_expansion_modules.resolution import resolve_architecture
from backend.nis.engineering.requirement_expansion_modules.resolution import resolve_safety_context
from backend.nis.engineering.requirement_expansion_modules.resolution import sensor_family
from backend.nis.engineering.requirement_expansion_modules.text_utils import extract_int
from backend.nis.engineering.requirement_expansion_modules.text_utils import now_iso
from backend.nis.engineering.requirement_expansion_modules.text_utils import normalize_text
from backend.nis.engineering.requirement_expansion_modules.text_utils import sha256_hex


def _resolve_required_coverage(text: str) -> float | None:
    return extract_int(
        text,
        (
            r"(\d+(?:[.,]\d+)?)\s*(?:grad|degree|°)\s*(?:um|umfeld|abdeckung|coverage)",
            r"umkreis\s*(?:von\s*)?(\d+(?:[.,]\d+)?)",
            r"surround(?:ing)?\s*(\d+(?:[.,]\d+)?)",
        ),
    )


def _assumptions_need_review(assumptions: list[dict[str, Any]]) -> bool:
    return any(item.get("requires_confirmation") for item in assumptions)


def expand_requirement(
    prompt: str,
    *,
    domain: str | None = None,
    model: str = "engineering-workload-orchestrator",
) -> dict[str, Any]:
    """Expand a requirement into a deterministic proposal payload."""
    normalized_prompt = normalize_text(prompt)
    resolved_domain = choose_domain(normalized_prompt, domain)
    resolved_family = sensor_family(normalized_prompt)
    safety_context = resolve_safety_context(normalized_prompt, resolved_domain)
    architecture = resolve_architecture(normalized_prompt)
    generation_policy = resolve_generation_policy(
        normalized_prompt,
        industry=domain,
        bus_types=[] if architecture.get("technology") == "AUTO_SELECT" else [architecture.get("technology")],
    )
    generation_industry = generation_policy["industry"]["id"] or resolved_domain

    required_coverage = _resolve_required_coverage(normalized_prompt)

    assumptions = derive_assumptions(
        generation_industry,
        normalized_prompt,
        resolved_family,
        required_coverage,
        safety_context=safety_context,
        architecture=architecture,
    )
    ambiguities = derive_ambiguity(generation_industry, normalized_prompt, resolved_family)
    open_decisions = derive_open_decisions(ambiguities, assumptions)
    findings = derive_findings(resolved_family, assumptions, ambiguities)

    functions = derive_functions(normalized_prompt, resolved_family)
    sensors = derive_sensors(resolved_family, assumptions, normalized_prompt)
    coordinate_system = derive_coordinate_system(resolved_family)
    parameters = derive_parameters(normalized_prompt, resolved_family, assumptions)
    status_models = derive_status_models(resolved_family)
    data_objects = derive_data_objects(resolved_family, functions)
    signals = derive_signals(resolved_family, functions)
    hardware = derive_hardware(resolved_family, functions)
    capacity = derive_capacity(resolved_family, sensors, parameters)
    communications = derive_communications(resolved_family, capacity, sensors)
    messages = derive_messages(capacity, resolved_family)
    routing = derive_routing(normalized_prompt, hardware, communications)

    assumptions_status = "REQUIRED_REVIEW" if _assumptions_need_review(assumptions) else "COMPLETED"
    open_decisions_status = "REQUIRED_REVIEW" if open_decisions else "COMPLETED"
    workflow_status = "WAITING_FOR_INPUT" if open_decisions_status == "REQUIRED_REVIEW" else "READY_FOR_REVIEW"

    if workflow_status == "WAITING_FOR_INPUT":
        status = "OK"
        interpretation_status = "INCOMPLETE"
    else:
        status = "OK"
        interpretation_status = "COMPLETE"

    interpretation = {
        "raw_prompt": prompt,
        "normalized_prompt": normalized_prompt,
        "resolved_domain": resolved_domain,
        "resolved_family": resolved_family,
        "safety_context": safety_context,
        "architecture_hint": architecture,
        "generation_policy": generation_policy,
        "model": model,
        "status": interpretation_status,
        "created_at": now_iso(),
    }

    payload = {
        "status": status,
        "workflow_status": workflow_status,
        "interpretation": interpretation,
        "ambiguity": ambiguities,
        "assumptions": assumptions,
        "functions": functions,
        "sensors": sensors,
        "coordinate_system": coordinate_system,
        "parameters": parameters,
        "status_models": status_models,
        "data_objects": data_objects,
        "signals": signals,
        "hardware": hardware,
        "communications": communications,
        "messages": messages,
        "routing": routing,
        "capacity": capacity,
        "open_decisions": open_decisions,
        "findings": findings,
        "provenance": {
            "engine_version": ENGINE_VERSION,
            "engine_workflow_statuses": WORKFLOW_STATUSES,
            "requested_at": now_iso(),
            "seed": sha256_hex(normalized_prompt + ":" + (domain or "") + ":" + (model or "")),
        },
        "confidence": round(0.99 if not ambiguities else 0.83, 3),
        "assumptions_status": assumptions_status,
        "open_decisions_status": open_decisions_status,
    }
    payload["completion"] = derive_completion_report(payload)
    if payload["completion"]["blocking_findings"]:
        payload["workflow_status"] = "INCOMPLETE"
    return payload
