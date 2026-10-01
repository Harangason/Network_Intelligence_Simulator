"""Assumptions, ambiguities, and completion analysis for requirement expansion."""

from __future__ import annotations

from typing import Any


def derive_ambiguity(domain: str, text: str, resolved_family: str) -> list[dict[str, Any]]:
    ambiguities: list[dict[str, Any]] = []
    if resolved_family == "camera" and "360" not in text:
        ambiguities.append(
            {
                "topic": "coverage_scope",
                "status": "OPEN",
                "options": ["front_only", "front_rear", "full_surround_360"],
                "evidence": ["camera_coverage_was_not_explicitly_quantified"],
            }
        )
    if resolved_family in {"generic", "position", "camera", "lidar", "radar"} and "safety" not in text and "sicher" not in text:
        ambiguities.append(
            {
                "topic": "safety_relevance",
                "status": "OPEN",
                "options": ["safety_relevant", "non_safety", "safety_unknown"],
                "evidence": [f"domain_is_{domain.lower()}_neutral"],
            }
        )
    if resolved_family == "generic":
        ambiguities.append(
            {
                "topic": "technology_family",
                "status": "OPEN",
                "options": ["sensor_based", "software_only", "network_only", "manual_modeling_required"],
                "evidence": ["no_known_sensor_or_function_family_resolved"],
            }
        )
    return ambiguities


def derive_assumptions(
    resolved_domain: str,
    text: str,
    resolved_family: str,
    required_coverage: float | None,
    safety_context: dict[str, Any] | None = None,
    architecture: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    assumptions: list[dict[str, Any]] = []
    if resolved_family == "camera":
        industry_key = str(resolved_domain or "").strip().lower()
        reference_frames = {
            "automotive": "VehicleReferenceFrame",
            "industrial": "MachineCellReferenceFrame",
            "industrial_automation": "MachineCellReferenceFrame",
            "process_industry": "PlantReferenceFrame",
            "robotics_ros": "RobotBaseReferenceFrame",
            "aerospace": "PlatformReferenceFrame",
            "rail": "TrainReferenceFrame",
            "marine": "VesselReferenceFrame",
            "building_automation": "BuildingReferenceFrame",
            "energy": "EnergySiteReferenceFrame",
            "embedded_systems": "DeviceReferenceFrame",
            "iot_wireless": "SiteReferenceFrame",
            "generic": "SystemReferenceFrame",
            "generic_networking": "SystemReferenceFrame",
            "custom": "SystemReferenceFrame",
        }
        transport_policies = {
            "automotive": "raw_or_compressed_stream_on_ethernet_status_on_can_fd",
            "industrial": "stream_on_selected_industrial_ethernet_status_separate",
            "industrial_automation": "stream_on_selected_industrial_ethernet_status_separate",
            "process_industry": "stream_transport_and_process_status_require_separate_bindings",
            "robotics_ros": "typed_stream_over_dds_or_ethernet_status_separate",
            "aerospace": "qualified_stream_transport_and_status_bus_require_selection",
            "rail": "train_backbone_stream_and_control_status_require_separate_bindings",
            "marine": "ip_stream_and_navigation_status_require_separate_bindings",
            "building_automation": "ip_stream_and_building_status_require_separate_bindings",
            "energy": "stream_transport_and_grid_status_require_separate_bindings",
            "embedded_systems": "local_camera_link_and_control_status_require_separate_bindings",
        }
        if required_coverage is None:
            assumptions.append(
                {
                    "concept": "required_coverage",
                    "proposed_value": 360.0,
                    "reason": "No explicit coverage was provided.",
                    "confidence": 0.82,
                    "requires_confirmation": True,
                    "status": "REQUIRED_REVIEW",
                }
            )
        else:
            assumptions.append(
                {
                    "concept": "required_coverage",
                    "proposed_value": required_coverage,
                    "reason": "Coverage was explicitly specified in requirement text.",
                    "confidence": 0.97,
                    "requires_confirmation": False,
                    "status": "CONFIRMED",
                }
            )
        assumptions.append(
                {
                    "concept": "camera_operating_frame",
                    "proposed_value": reference_frames.get(industry_key, "SystemReferenceFrame"),
                    "reason": f"Spatial relation in {resolved_domain} requires an explicit fixed reference frame.",
                "confidence": 0.88,
                "requires_confirmation": True,
                "status": "REQUIRED_REVIEW",
            }
        )
        assumptions.append(
            {
                "concept": "frame_rate",
                "proposed_value": 30,
                "unit": "Hz",
                "reason": "No explicit frame-rate requirement.",
                "confidence": 0.61,
                "requires_confirmation": False,
                "status": "OPTIONAL",
            }
        )
        assumptions.append(
                {
                    "concept": "image_transport_policy",
                    "proposed_value": transport_policies.get(industry_key, "stream_transport_and_status_transport_require_selection"),
                    "reason": "Camera payload and status are separate meanings and require technology-specific bindings.",
                "confidence": 0.9,
                "requires_confirmation": True,
                "status": "REQUIRED_REVIEW",
            }
        )
    else:
        assumptions.append(
            {
                "concept": "sensor_positioning",
                "proposed_value": "best_effort",
                "reason": "No explicit sensor placement was specified.",
                "confidence": 0.66,
                "requires_confirmation": True,
                "status": "REQUIRED_REVIEW",
            }
        )
    if safety_context:
        assumptions.append(
            {
                "concept": "safety_context",
                "proposed_value": safety_context.get("level"),
                "reason": "Safety classification gates downstream review and validation depth.",
                "confidence": 0.78 if safety_context.get("requires_confirmation") else 0.92,
                "requires_confirmation": bool(safety_context.get("requires_confirmation")),
                "status": safety_context.get("status") or "UNKNOWN",
            }
        )
    if architecture:
        assumptions.append(
            {
                "concept": "network_architecture_hint",
                "proposed_value": architecture.get("technology"),
                "reason": f"Architecture source is {architecture.get('source')}.",
                "confidence": 0.95 if architecture.get("source") == "explicit" else 0.7,
                "requires_confirmation": architecture.get("technology") == "AUTO_SELECT",
                "status": "CONFIRMED" if architecture.get("source") == "explicit" else "REQUIRED_REVIEW",
            }
        )
    return assumptions


def derive_open_decisions(ambiguities: list[dict[str, Any]], assumptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for ambiguity in ambiguities:
        decisions.append(
            {
                "type": "ambiguity",
                "topic": ambiguity["topic"],
                "status": ambiguity["status"],
                "options": ambiguity["options"],
            }
        )
    for assumption in assumptions:
        if assumption.get("requires_confirmation"):
            decisions.append(
                {
                    "type": "assumption",
                    "topic": assumption["concept"],
                    "status": assumption["status"],
                    "proposed_value": assumption["proposed_value"],
                    "confidence": assumption["confidence"],
                }
            )
    return decisions


def derive_findings(
    resolved_family: str,
    assumptions: list[dict[str, Any]],
    ambiguities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not assumptions:
        findings.append({"code": "MISSING_ASSUMPTIONS", "severity": "ERROR", "message": "No engineering assumptions generated."})
    if not ambiguities:
        findings.append({"code": "ASSUMPTION_CLARITY", "severity": "INFO", "message": "No high-risk ambiguities detected in prompt."})
    else:
        findings.append({"code": "AMBIGUITY_DETECTED", "severity": "WARNING", "message": "Open ambiguities require user resolution."})
    if resolved_family not in {"camera", "temperature", "pressure", "position", "lidar", "radar", "ultrasonic", "generic"}:
        findings.append({"code": "UNKNOWN_SENSOR_FAMILY", "severity": "WARNING", "message": f"Unknown sensor family: {resolved_family}"})
    return findings


def derive_completion_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether the generated proposal is ready for human approval."""
    required_sections = (
        "interpretation",
        "assumptions",
        "functions",
        "sensors",
        "parameters",
        "status_models",
        "data_objects",
        "signals",
        "hardware",
        "communications",
        "messages",
        "routing",
        "capacity",
    )
    missing = [section for section in required_sections if not payload.get(section)]
    open_decisions = list(payload.get("open_decisions") or [])
    blocking_findings = [
        item for item in payload.get("findings") or []
        if str(item.get("severity") or "").upper() == "ERROR"
    ]
    complete = not missing and not blocking_findings
    return {
        "complete": complete,
        "missing_sections": missing,
        "blocking_findings": blocking_findings,
        "open_decision_count": len(open_decisions),
        "ready_for_human_review": complete,
        "ready_for_auto_apply": False,
        "completion_policy": "human_review_required_before_model_apply",
    }
