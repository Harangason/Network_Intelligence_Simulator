"""Separate persistence for AI-generated engineering proposals."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .models import (
    RELATABLE_OBJECT_TYPES,
    RELATION_TYPES,
    EngineeringValidationError,
    validate_choice,
    validate_uuid,
)
from .relations import create_relation
from .repository import (
    PARENT_LINKS,
    NotFoundError,
    create_object,
    get_object,
    get_spec,
)

PROPOSAL_STATUSES = (
    "AI_GENERATED",
    "DRAFT",
    "READY_FOR_REVIEW",
    "PARTIALLY_APPROVED",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
)

RESOURCE_OBJECT_TYPES = {
    "hardware-nodes": "HardwareNode",
    "functions": "Function",
    "interfaces": "Interface",
    "messages": "Message",
    "signals": "Signal",
}


def create_proposal(data: dict[str, Any]) -> dict[str, Any]:
    prompt = str(data.get("prompt") or "").strip()
    proposal_type = str(data.get("proposal_type") or "").strip()
    proposed_objects = data.get("proposed_objects")
    if not prompt or not proposal_type:
        raise EngineeringValidationError("proposal_type und prompt sind Pflichtfelder.")
    if not isinstance(proposed_objects, list) or not proposed_objects:
        raise EngineeringValidationError("proposed_objects muss eine nicht-leere Liste sein.")

    with get_connection() as conn:
        row = conn.execute(
            "INSERT INTO engineering_ai_proposals "
            "(proposal_type, target_object, prompt, model, model_version, retrieved_context, "
            "evidence, confidence, proposed_objects, validation_results, status, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AI_GENERATED', %s) "
            "RETURNING *",
            (
                proposal_type,
                Jsonb(data.get("target_object", {})),
                prompt,
                data.get("model"),
                data.get("model_version"),
                Jsonb(data.get("retrieved_context", [])),
                Jsonb(data.get("evidence", [])),
                data.get("confidence"),
                Jsonb(proposed_objects),
                Jsonb(data.get("validation_results", [])),
                data.get("created_by") or data.get("actor"),
            ),
        ).fetchone()
        conn.commit()
    return row


def get_proposal(proposal_id: str) -> dict[str, Any]:
    validate_uuid(proposal_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM engineering_ai_proposals WHERE proposal_id = %s", (proposal_id,)
        ).fetchone()
    if row is None:
        raise NotFoundError(f"AIProposal {proposal_id} nicht gefunden.")
    return row


def list_proposals(*, status: str | None = None, limit: int = 100, offset: int = 0):
    values: list[Any] = []
    where = ""
    if status:
        if status not in PROPOSAL_STATUSES:
            raise EngineeringValidationError(f"Unbekannter Proposal-Status: {status!r}.")
        where = " WHERE status = %s"
        values.append(status)
    values.extend((limit, offset))
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM engineering_ai_proposals"
            f"{where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            values,
        ).fetchall()


def _proposal_object_type(proposal: dict[str, Any], item: dict[str, Any]) -> str:
    target = proposal.get("target_object") or {}
    value = item.get("object_type") or RESOURCE_OBJECT_TYPES.get(str(item.get("resource") or target.get("resource") or ""))
    if value not in {*RELATABLE_OBJECT_TYPES, "Relation"}:
        raise EngineeringValidationError(f"Unbekannter Proposal-Objekttyp: {value!r}.")
    return str(value)


def _canonical_id_from_proposal_reference(value: Any) -> str | None:
    if not value:
        return None
    try:
        validate_uuid(str(value))
    except (EngineeringValidationError, ValueError):
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT proposed_objects FROM engineering_ai_proposals WHERE proposal_id = %s",
            (str(value),),
        ).fetchone()
    if row is None:
        return None
    for item in row.get("proposed_objects") or []:
        if isinstance(item, dict) and item.get("canonical_id"):
            return str(item["canonical_id"])
    return None


def _normalize_proposal_references(proposal: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    proposed_objects: list[dict[str, Any]] = []
    for raw_item in proposal.get("proposed_objects") or []:
        item = dict(raw_item) if isinstance(raw_item, dict) else {}
        try:
            object_type = _proposal_object_type(proposal, item)
        except EngineeringValidationError:
            proposed_objects.append(item)
            continue
        reference_fields = ["source_id", "target_id"] if object_type == "Relation" else []
        parent_link = PARENT_LINKS.get(object_type)
        if parent_link:
            reference_fields.append(parent_link[0])
        for field in reference_fields:
            resolved = _canonical_id_from_proposal_reference(item.get(field))
            if resolved and item.get(field) != resolved:
                item[field] = resolved
                changed = True
        proposed_objects.append(item)
    return {**proposal, "proposed_objects": proposed_objects}, changed


def validate_proposed_items(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    proposal, _ = _normalize_proposal_references(proposal)
    results: list[dict[str, Any]] = []
    for index, raw_item in enumerate(proposal.get("proposed_objects") or []):
        errors: list[str] = []
        item = dict(raw_item) if isinstance(raw_item, dict) else {}
        object_type = str(item.get("object_type") or "Unknown")
        try:
            object_type = _proposal_object_type(proposal, item)
            if object_type == "Relation":
                required = ("relation_type", "source_type", "source_id", "target_type", "target_id")
                missing = [field for field in required if not item.get(field)]
                if missing:
                    raise EngineeringValidationError(f"Pflichtfelder fehlen: {', '.join(missing)}")
                validate_choice(item["relation_type"], RELATION_TYPES, "relation_type")
                validate_choice(item["source_type"], RELATABLE_OBJECT_TYPES, "source_type")
                validate_choice(item["target_type"], RELATABLE_OBJECT_TYPES, "target_type")
                validate_uuid(str(item["source_id"]))
                validate_uuid(str(item["target_id"]))
                get_object(str(item["source_type"]), str(item["source_id"]))
                get_object(str(item["target_type"]), str(item["target_id"]))
            else:
                if not item.get("name"):
                    raise EngineeringValidationError("Pflichtfeld fehlt: 'name'")
                spec = get_spec(object_type)
                spec.validate(item)
                parent_link = PARENT_LINKS.get(object_type)
                if parent_link:
                    parent_field, parent_type, _ = parent_link
                    if item.get(parent_field):
                        get_object(parent_type, str(item[parent_field]))
        except (EngineeringValidationError, NotFoundError, ValueError) as error:
            errors.append(str(error))
        results.append({"index": index, "object_type": object_type, "valid": not errors, "errors": errors})
    return results


def _update_proposal_row(
    proposal_id: str,
    *,
    proposed_objects: list[dict[str, Any]] | None = None,
    validation_results: list[dict[str, Any]] | None = None,
    status: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    assignments = ["modified_at = now()", "modified_by = %s"]
    values: list[Any] = [actor]
    if proposed_objects is not None:
        assignments.append("proposed_objects = %s")
        values.append(Jsonb(proposed_objects))
    if validation_results is not None:
        assignments.append("validation_results = %s")
        values.append(Jsonb(validation_results))
    if status is not None:
        if status not in PROPOSAL_STATUSES:
            raise EngineeringValidationError(f"Unbekannter Proposal-Status: {status!r}.")
        assignments.append("status = %s")
        values.append(status)
    values.append(proposal_id)
    with get_connection() as conn:
        row = conn.execute(
            f"UPDATE engineering_ai_proposals SET {', '.join(assignments)} WHERE proposal_id = %s RETURNING *",
            values,
        ).fetchone()
        conn.commit()
    if row is None:
        raise NotFoundError(f"AIProposal {proposal_id} nicht gefunden.")
    return row


def update_proposal(proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal["status"] in {"APPROVED", "SUPERSEDED"}:
        raise EngineeringValidationError("Freigegebene oder abgeloeste Vorschlaege sind unveraenderlich.")
    proposed_objects = data.get("proposed_objects", proposal.get("proposed_objects") or [])
    if not isinstance(proposed_objects, list) or not proposed_objects:
        raise EngineeringValidationError("proposed_objects muss eine nicht-leere Liste sein.")
    return _update_proposal_row(
        proposal_id,
        proposed_objects=proposed_objects,
        validation_results=[],
        status="DRAFT",
        actor=data.get("actor"),
    )


def validate_proposal(proposal_id: str, *, actor: str | None = None) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    proposal, changed = _normalize_proposal_references(proposal)
    results = validate_proposed_items(proposal)
    status = "READY_FOR_REVIEW" if results and all(item["valid"] for item in results) else "DRAFT"
    return _update_proposal_row(
        proposal_id,
        proposed_objects=proposal.get("proposed_objects") if changed else None,
        validation_results=results,
        status=status,
        actor=actor,
    )


def approve_proposal(
    proposal_id: str,
    *,
    indexes: list[int] | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal["status"] in {"REJECTED", "SUPERSEDED"}:
        raise EngineeringValidationError("Abgelehnte oder abgeloeste Vorschlaege koennen nicht freigegeben werden.")
    proposal, changed = _normalize_proposal_references(proposal)
    if changed:
        proposal = _update_proposal_row(
            proposal_id,
            proposed_objects=proposal.get("proposed_objects") or [],
            validation_results=[],
            status="DRAFT",
            actor=actor,
        )
    validation = validate_proposed_items(proposal)
    selected = set(indexes if indexes is not None else [item["index"] for item in validation if item["valid"]])
    proposed_objects = [dict(item) for item in proposal.get("proposed_objects") or []]
    valid_indexes = {item["index"] for item in validation if item["valid"]}
    invalid_selection = selected - valid_indexes
    if invalid_selection:
        raise EngineeringValidationError(f"Nicht valide Proposal-Eintraege ausgewaehlt: {sorted(invalid_selection)}")
    if not selected:
        raise EngineeringValidationError("Keine validen Proposal-Eintraege zur Freigabe ausgewaehlt.")

    for index in sorted(selected):
        item = proposed_objects[index]
        if item.get("canonical_id"):
            continue
        object_type = _proposal_object_type(proposal, item)
        provenance = {
            **dict(item.get("provenance") or {}),
            "proposal_id": proposal_id,
            "prompt": proposal.get("prompt"),
            "model": proposal.get("model"),
            "evidence": proposal.get("evidence") or [],
            "approved_by": actor,
        }
        payload = {
            key: value
            for key, value in item.items()
            if key not in {"object_type", "resource", "canonical_id", "proposal_state"}
        }
        payload.update(
            {
                "source": "ai_generated",
                "provenance": provenance,
                "review_state": "reviewed",
                "approval_state": "approved",
                "actor": actor,
            }
        )
        created = create_relation(payload) if object_type == "Relation" else create_object(object_type, payload)
        item["canonical_id"] = str(created.get("id"))
        item["proposal_state"] = "APPROVED"
        proposed_objects[index] = item
        _update_proposal_row(proposal_id, proposed_objects=proposed_objects, validation_results=validation, status="PARTIALLY_APPROVED", actor=actor)

    approved_count = sum(bool(item.get("canonical_id")) for item in proposed_objects)
    status = "APPROVED" if approved_count == len(proposed_objects) else "PARTIALLY_APPROVED"
    return _update_proposal_row(
        proposal_id,
        proposed_objects=proposed_objects,
        validation_results=validation,
        status=status,
        actor=actor,
    )


def approve_all_valid_proposals(*, actor: str | None = None) -> list[dict[str, Any]]:
    approved = []
    for _ in range(6):
        progressed = False
        proposals = list_proposals(limit=1000)
        for proposal in proposals:
            if proposal["status"] in {"AI_GENERATED", "DRAFT", "READY_FOR_REVIEW", "PARTIALLY_APPROVED"}:
                proposal, changed = _normalize_proposal_references(proposal)
                if changed:
                    proposal = _update_proposal_row(
                        str(proposal["proposal_id"]),
                        proposed_objects=proposal.get("proposed_objects") or [],
                        validation_results=[],
                        status="DRAFT",
                        actor=actor,
                    )
                validation = validate_proposed_items(proposal)
                indexes = [item["index"] for item in validation if item["valid"]]
                pending = [index for index in indexes if not (proposal.get("proposed_objects") or [])[index].get("canonical_id")]
                if pending:
                    approved.append(approve_proposal(str(proposal["proposal_id"]), indexes=pending, actor=actor))
                    progressed = True
        if not progressed:
            break
    return approved


def reject_proposal(proposal_id: str, *, actor: str | None = None) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal["status"] == "APPROVED":
        raise EngineeringValidationError("Freigegebene Vorschlaege koennen nicht nachtraeglich abgelehnt werden.")
    return _update_proposal_row(proposal_id, status="REJECTED", actor=actor)
