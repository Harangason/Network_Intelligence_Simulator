"""Structure-tree evaluation and canonical hierarchy assignment service."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .models import EngineeringValidationError
from .proposals import (
    create_proposal,
    get_proposal,
    list_proposals,
    record_proposal_decision,
    update_proposal,
    validate_proposal,
)
from .relations import list_relations
from .repository import PARENT_LINKS, get_object, update_object
from .structure_rules import (
    infer_device_type,
    recommend_structure_name,
    score_structure_parent,
)

STRUCTURE_TYPES = ("HardwareNode", "Function", "Interface", "Message", "Signal")
STRUCTURE_MODEL = "structure-learner"
STRUCTURE_MODEL_VERSION = "1.0"


def _learning_key(child: dict[str, Any], parent: dict[str, Any], relation_type: str) -> str:
    def normalized(value: Any) -> str:
        return "-".join(
            token
            for token in re.split(r"[^a-z0-9]+", str(value or "").lower())
            if len(token) > 2
        )

    return f"{relation_type}:{normalized(parent.get('name'))}>{normalized(child.get('name'))}"


def _reviewed_examples() -> tuple[Counter[str], Counter[str], int, int]:
    accepted: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    accepted_proposals = 0
    rejected_proposals = 0
    for proposal in list_proposals(limit=1000):
        if proposal.get("proposal_type") != "STRUCTURE_TREE":
            continue
        status = str(proposal.get("status") or "")
        if status == "APPROVED":
            accepted_proposals += 1
        elif status == "REJECTED":
            rejected_proposals += 1
        else:
            continue
        target = accepted if status == "APPROVED" else rejected
        for item in proposal.get("proposed_objects") or []:
            if isinstance(item, dict) and item.get("learning_key"):
                target[str(item["learning_key"])] += 1
    return accepted, rejected, accepted_proposals, rejected_proposals


def _selection_objects(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = data.get("selections")
    if not isinstance(raw, dict):
        raise EngineeringValidationError("selections muss ein Objekt sein.")
    result: dict[str, list[dict[str, Any]]] = {}
    for object_type in STRUCTURE_TYPES:
        ids = raw.get(object_type, [])
        if not isinstance(ids, list):
            raise EngineeringValidationError(f"selections.{object_type} muss eine Liste sein.")
        unique_ids = list(dict.fromkeys(str(value) for value in ids if value))
        result[object_type] = [get_object(object_type, object_id) for object_id in unique_ids]
    if len(result["HardwareNode"]) != 1:
        raise EngineeringValidationError("Genau ein Hardware-Knoten muss ausgewählt sein.")
    for object_type in STRUCTURE_TYPES[1:]:
        if not result[object_type]:
            raise EngineeringValidationError(f"Mindestens ein {object_type}-Objekt muss ausgewählt sein.")
    return result


def evaluate_structure(data: dict[str, Any]) -> dict[str, Any]:
    selections = _selection_objects(data)
    accepted, rejected, accepted_count, rejected_count = _reviewed_examples()
    suggestions: list[dict[str, Any]] = []
    proposed_objects: list[dict[str, Any]] = []

    for child_type in STRUCTURE_TYPES[1:]:
        parent_field, parent_type, relation_type = PARENT_LINKS[child_type]
        parents = selections[parent_type]
        for child in selections[child_type]:
            ranked: list[tuple[float, dict[str, Any], list[str], str]] = []
            for parent in parents:
                learning_key = _learning_key(child, parent, relation_type)
                score, reasons = score_structure_parent(
                    child,
                    parent,
                    current_parent_id=str(child.get(parent_field) or "") or None,
                    accepted_examples=accepted[learning_key],
                    rejected_examples=rejected[learning_key],
                )
                ranked.append((score, parent, reasons, learning_key))
            score, parent, reasons, learning_key = max(ranked, key=lambda item: item[0])
            suggestion = {
                "child_type": child_type,
                "child_id": str(child["id"]),
                "child_name": child["name"],
                "parent_type": parent_type,
                "parent_id": str(parent["id"]),
                "parent_name": parent["name"],
                "parent_field": parent_field,
                "relation_type": relation_type,
                "confidence": score,
                "reason": ", ".join(reasons),
                "current_name": child["name"],
                "recommended_name": recommend_structure_name(child_type, child, parent),
                "learning_key": learning_key,
            }
            suggestions.append(suggestion)
            proposed_objects.append(
                {
                    "object_type": "Relation",
                    "relation_type": relation_type,
                    "source_type": parent_type,
                    "source_id": str(parent["id"]),
                    "target_type": child_type,
                    "target_id": str(child["id"]),
                    "confidence": score,
                    "learning_key": learning_key,
                    "recommended_name": suggestion["recommended_name"],
                }
            )

    hardware = selections["HardwareNode"][0]
    inferred_device_type = infer_device_type(
        str(hardware["name"]),
        str(hardware.get("device_type") or "GenericDevice"),
    )
    average_confidence = round(
        sum(float(item["confidence"]) for item in suggestions) / len(suggestions),
        2,
    )
    proposal = create_proposal(
        {
            "proposal_type": "STRUCTURE_TREE",
            "target_object": {
                "resource": "structure-tree",
                "hardware_node_id": str(hardware["id"]),
            },
            "prompt": "Bewerte und ordne die ausgewählte Engineering-Hierarchie.",
            "model": STRUCTURE_MODEL,
            "model_version": STRUCTURE_MODEL_VERSION,
            "confidence": average_confidence,
            "retrieved_context": [
                {"accepted_structure_reviews": accepted_count},
                {"rejected_structure_reviews": rejected_count},
            ],
            "evidence": [
                {"type": "canonical_parent_fields", "count": len(suggestions)},
                {"type": "reviewed_structure_feedback", "count": accepted_count + rejected_count},
            ],
            "proposed_objects": proposed_objects,
            "created_by": data.get("actor") or "structure-tree-ai",
        }
    )
    proposal = validate_proposal(str(proposal["proposal_id"]), actor="structure-tree-ai")
    return {
        "proposal_id": str(proposal["proposal_id"]),
        "model": STRUCTURE_MODEL,
        "model_version": STRUCTURE_MODEL_VERSION,
        "confidence": average_confidence,
        "suggestions": suggestions,
        "hardware_adjustments": [
            {
                "object_type": "HardwareNode",
                "id": str(hardware["id"]),
                "name": hardware["name"],
                "field": "device_type",
                "current_value": hardware.get("device_type"),
                "suggested_value": inferred_device_type,
                "reason": "Gerätetyp aus dem kanonischen Namen abgeleitet",
            }
        ],
        "learning": {
            "accepted": accepted_count,
            "rejected": rejected_count,
            "reviewed": accepted_count + rejected_count,
        },
    }


def _proposal_item(assignment: dict[str, Any], relation_id: str | None = None) -> dict[str, Any]:
    item = {
        "object_type": "Relation",
        "relation_type": assignment["relation_type"],
        "source_type": assignment["parent_type"],
        "source_id": assignment["parent_id"],
        "target_type": assignment["child_type"],
        "target_id": assignment["child_id"],
        "confidence": assignment.get("confidence"),
        "learning_key": assignment.get("learning_key"),
        "recommended_name": assignment.get("recommended_name"),
    }
    if relation_id:
        item.update({"canonical_id": relation_id, "proposal_state": "APPROVED"})
    return item


def apply_structure(data: dict[str, Any]) -> dict[str, Any]:
    assignments = data.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise EngineeringValidationError("assignments muss eine nicht-leere Liste sein.")
    proposal_id = str(data.get("proposal_id") or "").strip() or None
    if proposal_id:
        proposal = get_proposal(proposal_id)
        if proposal.get("proposal_type") != "STRUCTURE_TREE":
            raise EngineeringValidationError("Der Vorschlag gehört nicht zum Structure Tree.")
    actor = str(data.get("actor") or "structure-tree")

    normalized_assignments = [dict(item) for item in assignments if isinstance(item, dict)]
    if len(normalized_assignments) != len(assignments):
        raise EngineeringValidationError("Jede Structure-Zuordnung muss ein Objekt sein.")
    for assignment in normalized_assignments:
        child_type = str(assignment.get("child_type") or "")
        child_id = str(assignment.get("child_id") or "")
        parent_type = str(assignment.get("parent_type") or "")
        parent_id = str(assignment.get("parent_id") or "")
        parent_link = PARENT_LINKS.get(child_type)
        if not parent_link or parent_link[1] != parent_type:
            raise EngineeringValidationError(
                f"Ungültige Hierarchiekante: {parent_type} -> {child_type}."
            )
        get_object(child_type, child_id)
        get_object(parent_type, parent_id)

    for raw_update in data.get("object_updates") or []:
        if not isinstance(raw_update, dict):
            continue
        object_type = str(raw_update.get("object_type") or "")
        object_id = str(raw_update.get("id") or "")
        updates = raw_update.get("updates")
        if object_type not in STRUCTURE_TYPES or not object_id or not isinstance(updates, dict):
            raise EngineeringValidationError("Ungültiges Objekt-Update im Structure Tree.")
        allowed = {"name"}
        if object_type == "HardwareNode":
            allowed.add("device_type")
        safe_updates = {key: value for key, value in updates.items() if key in allowed}
        if safe_updates:
            update_object(
                object_type,
                object_id,
                {**safe_updates, "actor": actor, "change_summary": "structure tree adjustment"},
            )

    applied: list[dict[str, Any]] = []
    proposal_objects: list[dict[str, Any]] = []
    order = {object_type: index for index, object_type in enumerate(STRUCTURE_TYPES)}
    normalized_assignments = sorted(
        normalized_assignments,
        key=lambda item: order.get(str(item.get("child_type")), 99),
    )
    for assignment in normalized_assignments:
        child_type = str(assignment.get("child_type") or "")
        child_id = str(assignment.get("child_id") or "")
        parent_type = str(assignment.get("parent_type") or "")
        parent_id = str(assignment.get("parent_id") or "")
        parent_link = PARENT_LINKS.get(child_type)
        if not parent_link or parent_link[1] != parent_type:
            raise EngineeringValidationError(
                f"Ungültige Hierarchiekante: {parent_type} -> {child_type}."
            )
        parent_field, _, relation_type = parent_link
        child = get_object(child_type, child_id)
        parent = get_object(parent_type, parent_id)
        updates: dict[str, Any] = {parent_field: parent_id}
        requested_name = str(assignment.get("name") or "").strip()
        if requested_name and requested_name != child.get("name"):
            updates["name"] = requested_name
        confidence = assignment.get("confidence")
        update_object(
            child_type,
            child_id,
            {
                **updates,
                "actor": actor,
                "change_summary": "structure tree assignment",
                "relation_source": "ai_generated" if proposal_id else "manual",
                "relation_confidence": confidence,
                "relation_provenance": {
                    "origin": "structure-tree",
                    "proposal_id": proposal_id,
                    "model": STRUCTURE_MODEL if proposal_id else None,
                },
                "relation_attributes": {
                    "name": f"{parent['name']} -> {requested_name or child['name']}",
                    "structure_tree": True,
                },
            },
        )
        relations = list_relations(
            object_type=child_type,
            object_id=child_id,
            relation_type=relation_type,
            limit=20,
        )
        relation = next(
            (
                item
                for item in relations
                if str(item.get("source_id")) == parent_id
                and str(item.get("target_id")) == child_id
            ),
            None,
        )
        enriched = {
            **assignment,
            "relation_type": relation_type,
            "parent_field": parent_field,
            "parent_name": parent["name"],
            "child_name": requested_name or child["name"],
            "learning_key": _learning_key(
                {**child, "name": requested_name or child["name"]},
                parent,
                relation_type,
            ),
        }
        applied.append({**enriched, "relation_id": str(relation["id"]) if relation else None})
        proposal_objects.append(
            _proposal_item(enriched, str(relation["id"]) if relation else None)
        )

    if proposal_id:
        proposal = update_proposal(proposal_id, {"proposed_objects": proposal_objects, "actor": actor})
        proposal = validate_proposal(proposal_id, actor=actor)
        proposal = record_proposal_decision(
            proposal_id,
            accepted=True,
            actor=actor,
            proposed_objects=proposal_objects,
        )
    else:
        proposal = None
    return {
        "proposal": proposal,
        "applied": applied,
        "count": len(applied),
    }


def reject_structure_proposal(proposal_id: str, *, actor: str | None = None) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal.get("proposal_type") != "STRUCTURE_TREE":
        raise EngineeringValidationError("Der Vorschlag gehört nicht zum Structure Tree.")
    return record_proposal_decision(
        proposal_id,
        accepted=False,
        actor=actor or "structure-tree-reviewer",
    )
