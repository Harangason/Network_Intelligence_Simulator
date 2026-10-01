"""Reversible canonicalization of semantically duplicate hardware systems."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .models import EngineeringValidationError, validate_uuid
from .project_context import current_project_id
from .repository import ENTITY_SPECS, _write_version_snapshot
from .structure_transfer import analyze_system_duplicates

MERGE_MODEL = "semantic-system-merge"
MERGE_MODEL_VERSION = "1.0"


def _merge_provenance(
    provenance: Any,
    *,
    actor: str,
    canonical_id: str,
    canonical_name: str,
    duplicate_id: str,
    duplicate_name: str,
    role: str,
) -> dict[str, Any]:
    result = dict(provenance) if isinstance(provenance, dict) else {}
    result["canonical_system_merge"] = {
        "role": role,
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "duplicate_id": duplicate_id,
        "duplicate_name": duplicate_name,
        "actor": actor,
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "reversible": True,
    }
    return result


def merge_system_duplicate(data: dict[str, Any]) -> dict[str, Any]:
    """Mark a duplicate as superseded and preserve it through an alias relation."""

    canonical_id = validate_uuid(data.get("canonical_hardware_id"))
    duplicate_id = validate_uuid(data.get("duplicate_hardware_id"))
    if canonical_id == duplicate_id:
        raise EngineeringValidationError("Kanonisches System und Dublette müssen verschieden sein.")
    actor = str(data.get("actor") or "structure-tree-reviewer")
    candidate_key = str(data.get("candidate_key") or "")

    candidate = next(
        (
            item
            for item in analyze_system_duplicates().get("items") or []
            if str(item.get("candidate_key")) == candidate_key
            and str(item.get("canonical_hardware", {}).get("id")) == canonical_id
            and str(item.get("duplicate_hardware", {}).get("id")) == duplicate_id
        ),
        None,
    )
    if not candidate:
        raise EngineeringValidationError(
            "Die Dublettenbewertung ist nicht mehr aktuell. Bitte die Systemprüfung aktualisieren."
        )

    project_id = current_project_id()
    with get_connection() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
            (project_id, "semantic-system-merge"),
        )
        rows = conn.execute(
            "SELECT * FROM engineering_hardware_nodes "
            "WHERE project_id = %s AND id IN (%s, %s) FOR UPDATE",
            (project_id, canonical_id, duplicate_id),
        ).fetchall()
        by_id = {str(row["id"]): row for row in rows}
        canonical = by_id.get(canonical_id)
        duplicate = by_id.get(duplicate_id)
        if not canonical or not duplicate:
            raise EngineeringValidationError("Mindestens eines der Systeme existiert nicht mehr.")

        canonical_provenance = _merge_provenance(
            canonical.get("provenance"),
            actor=actor,
            canonical_id=canonical_id,
            canonical_name=str(canonical["name"]),
            duplicate_id=duplicate_id,
            duplicate_name=str(duplicate["name"]),
            role="canonical",
        )
        canonical = conn.execute(
            "UPDATE engineering_hardware_nodes SET provenance = %s, confidence = GREATEST(COALESCE(confidence, 0), %s), "
            "version = version + 1, modified_at = now(), modified_by = %s "
            "WHERE project_id = %s AND id = %s RETURNING *",
            (Jsonb(canonical_provenance), candidate.get("confidence"), actor, project_id, canonical_id),
        ).fetchone()

        duplicate_provenance = _merge_provenance(
            duplicate.get("provenance"),
            actor=actor,
            canonical_id=canonical_id,
            canonical_name=str(canonical["name"]),
            duplicate_id=duplicate_id,
            duplicate_name=str(duplicate["name"]),
            role="alias",
        )
        duplicate = conn.execute(
            "UPDATE engineering_hardware_nodes SET lifecycle_state = 'superseded', provenance = %s, "
            "version = version + 1, modified_at = now(), modified_by = %s "
            "WHERE project_id = %s AND id = %s RETURNING *",
            (Jsonb(duplicate_provenance), actor, project_id, duplicate_id),
        ).fetchone()

        hardware_spec = ENTITY_SPECS["HardwareNode"]
        _write_version_snapshot(
            conn,
            hardware_spec,
            canonical,
            changed_by=actor,
            summary=f"{duplicate['name']} als kanonischen Alias übernommen",
        )
        _write_version_snapshot(
            conn,
            hardware_spec,
            duplicate,
            changed_by=actor,
            summary=f"Durch {canonical['name']} ersetzt",
        )

        relation = conn.execute(
            "INSERT INTO engineering_relations "
            "(project_id, relation_type, source_type, source_id, target_type, target_id, attributes, source, "
            "provenance, confidence, review_state, approval_state, created_by) "
            "VALUES (%s, 'CANONICAL_ALIAS_OF', 'HardwareNode', %s, 'HardwareNode', %s, %s, 'ai_generated', "
            "%s, %s, 'reviewed', 'approved', %s) "
            "ON CONFLICT (project_id, relation_type, source_type, source_id, target_type, target_id) "
            "DO UPDATE SET attributes = EXCLUDED.attributes, provenance = EXCLUDED.provenance, "
            "confidence = EXCLUDED.confidence, review_state = 'reviewed', approval_state = 'approved' "
            "RETURNING id",
            (
                project_id,
                duplicate_id,
                canonical_id,
                Jsonb({"reversible": True, "reason": candidate.get("reason")}),
                Jsonb({"model": MERGE_MODEL, "model_version": MERGE_MODEL_VERSION, "actor": actor}),
                candidate.get("confidence"),
                actor,
            ),
        ).fetchone()

        result = {
            "canonical_hardware": {"id": canonical_id, "name": canonical["name"]},
            "superseded_hardware": {"id": duplicate_id, "name": duplicate["name"]},
            "relation_id": str(relation["id"]),
            "confidence": candidate.get("confidence"),
            "reversible": True,
        }
        proposal = conn.execute(
            "INSERT INTO engineering_ai_proposals "
            "(project_id, proposal_type, target_object, prompt, model, model_version, evidence, confidence, "
            "proposed_objects, validation_results, status, created_by, modified_by) "
            "VALUES (%s, 'SYSTEM_MERGE', %s, %s, %s, %s, %s, %s, %s, %s, 'APPROVED', %s, %s) "
            "RETURNING proposal_id",
            (
                project_id,
                Jsonb({"object_type": "HardwareNode", "object_id": canonical_id}),
                f"Bestätigte kanonische Zusammenführung von {duplicate['name']} in {canonical['name']}",
                MERGE_MODEL,
                MERGE_MODEL_VERSION,
                Jsonb([candidate]),
                candidate.get("confidence"),
                Jsonb([result]),
                Jsonb([{"valid": True, "message": "Reversible Alias-Relation wurde gespeichert."}]),
                actor,
                actor,
            ),
        ).fetchone()
        result["proposal_id"] = str(proposal["proposal_id"])
        return result
