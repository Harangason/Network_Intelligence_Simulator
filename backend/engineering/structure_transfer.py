"""AI-assisted transfer of one ECU hierarchy to individually reviewed target ECUs."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .models import EngineeringValidationError
from .proposals import create_proposal, get_proposal, list_proposals, record_proposal_decision, update_proposal
from .repository import BASE_COLUMNS, PARENT_LINKS, create_object, get_object, get_spec, list_objects
from .structure_rules import (
    adapt_structure_name,
    equivalent_system_names,
    semantic_name_signature,
    semantic_name_similarity,
)

TRANSFER_TYPES = ("HardwareNode", "Function", "Interface", "Message", "Signal")
TRANSFER_MODEL = "semantic-structure-transfer"
TRANSFER_MODEL_VERSION = "1.1"
DUPLICATE_THRESHOLD = 0.78
CONTEXT_CONFLICT_CAP = 0.64
SYSTEM_STRUCTURE_DUPLICATE_THRESHOLD = 0.82


def _is_ecu(item: dict[str, Any]) -> bool:
    return str(item.get("device_type") or "") in {"ECU", "EmbeddedController"} or "ecu" in str(item.get("name") or "").lower()


def _learning_key(
    object_type: str,
    source_name: str,
    target_name: str | None,
    *,
    source_context: str,
    target_context: str,
) -> str:
    source = "-".join(semantic_name_signature(source_name, context=source_context)) or "generic"
    target = "-".join(semantic_name_signature(target_name, context=target_context)) if target_name else "create"
    return f"transfer:{object_type}:{source}>{target or 'generic'}"


def _reviewed_transfer_examples() -> tuple[Counter[str], Counter[str], int, int]:
    accepted: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    accepted_proposals = 0
    rejected_proposals = 0
    for proposal in list_proposals(limit=2000):
        if proposal.get("proposal_type") != "STRUCTURE_REPLICATION":
            continue
        status = str(proposal.get("status") or "")
        if status == "APPROVED":
            accepted_proposals += 1
            default_target = accepted
        elif status == "REJECTED":
            rejected_proposals += 1
            default_target = rejected
        else:
            continue
        for item in proposal.get("proposed_objects") or []:
            if isinstance(item, dict) and item.get("learning_key"):
                item_target = default_target
                if status == "APPROVED" and (
                    item.get("resolved_action") == "skip"
                    or (item.get("suggested_action") == "reuse" and item.get("action") != "reuse")
                ):
                    item_target = rejected
                item_target[str(item["learning_key"])] += 1
    return accepted, rejected, accepted_proposals, rejected_proposals


def _load_graph() -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    objects = {object_type: list_objects(object_type, limit=5000) for object_type in TRANSFER_TYPES}
    by_id = {str(item["id"]): item for group in objects.values() for item in group}
    children: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for object_type in TRANSFER_TYPES[1:]:
        parent_field, _, _ = PARENT_LINKS[object_type]
        for item in objects[object_type]:
            parent_id = str(item.get(parent_field) or "")
            if parent_id:
                children.setdefault((object_type, parent_id), []).append(item)
    for group in children.values():
        group.sort(key=lambda item: str(item.get("name") or "").lower())
    return objects, by_id, children


def _system_profile(
    hardware: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    children: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Describe one ECU by portable descendant roles, independent of its own name."""

    signatures: set[str] = set()
    counts: Counter[str] = Counter()
    frontier = [str(hardware["id"])]
    for object_type in TRANSFER_TYPES[1:]:
        next_frontier: list[str] = []
        for parent_id in frontier:
            parent = by_id.get(parent_id, hardware)
            for child in children.get((object_type, parent_id), []):
                signature = semantic_name_signature(child.get("name"), context=parent.get("name"))
                portable_name = ":".join(signature) or "generic"
                technical = ""
                if object_type == "Interface":
                    technical = str(child.get("interface_type") or "").casefold()
                elif object_type == "Message":
                    technical = ":".join(
                        str(child.get(field) or "").casefold()
                        for field in ("direction", "dlc_bytes")
                    )
                elif object_type == "Signal":
                    technical = ":".join(
                        str(child.get(field) or "").casefold()
                        for field in ("length_bits", "unit", "data_type")
                    )
                signatures.add(f"{object_type}:{portable_name}:{technical}")
                counts[object_type] += 1
                next_frontier.append(str(child["id"]))
        frontier = next_frontier
    return {
        "signatures": signatures,
        "counts": dict(counts),
        "total": sum(counts.values()),
    }


def _set_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right), 2)


def analyze_system_duplicates() -> dict[str, Any]:
    """Find semantically equivalent ECUs without mutating or merging the model."""

    objects, by_id, children = _load_graph()
    hardware = [
        item
        for item in objects["HardwareNode"]
        if _is_ecu(item) and item.get("lifecycle_state") != "superseded"
    ]
    profiles = {
        str(item["id"]): _system_profile(item, by_id, children)
        for item in hardware
    }
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(hardware):
        for right in hardware[index + 1:]:
            semantic_duplicate, name_similarity = equivalent_system_names(
                left.get("name"),
                right.get("name"),
            )
            left_profile = profiles[str(left["id"])]
            right_profile = profiles[str(right["id"])]
            structure_similarity = _set_similarity(
                left_profile["signatures"],
                right_profile["signatures"],
            )
            same_domain = bool(left.get("domain")) and left.get("domain") == right.get("domain")
            same_device_type = bool(left.get("device_type")) and left.get("device_type") == right.get("device_type")
            metadata_similarity = (int(same_domain) + int(same_device_type)) / 2
            structural_duplicate = (
                name_similarity >= 0.42
                and structure_similarity >= SYSTEM_STRUCTURE_DUPLICATE_THRESHOLD
                and min(left_profile["total"], right_profile["total"]) >= 4
            )
            if not semantic_duplicate and not structural_duplicate:
                continue

            def canonical_rank(item: dict[str, Any]) -> tuple[int, int, int, str]:
                profile = profiles[str(item["id"])]
                return (
                    int(profile["total"]),
                    int(item.get("approval_state") == "approved"),
                    int(item.get("review_state") == "reviewed"),
                    str(item.get("name") or ""),
                )

            canonical, duplicate = sorted((left, right), key=canonical_rank, reverse=True)
            canonical_profile = profiles[str(canonical["id"])]
            duplicate_profile = profiles[str(duplicate["id"])]
            confidence = round(min(0.99, name_similarity * 0.72 + structure_similarity * 0.18 + metadata_similarity * 0.10), 2)
            if semantic_duplicate and not left_profile["total"] == right_profile["total"]:
                reason = "Fachsynonyme erkannt; die Unterstruktur ist nur bei einem System vollständig gepflegt."
            elif structural_duplicate:
                reason = "Fachlich verwandte Benennung und weitgehend identische technische Unterstruktur."
            else:
                reason = "Kontrollierte Fachsynonyme bezeichnen dasselbe technische System."
            candidates.append(
                {
                    "candidate_key": ":".join(sorted((str(left["id"]), str(right["id"])))),
                    "canonical_hardware": {
                        "id": str(canonical["id"]),
                        "name": canonical["name"],
                        "child_count": canonical_profile["total"],
                    },
                    "duplicate_hardware": {
                        "id": str(duplicate["id"]),
                        "name": duplicate["name"],
                        "child_count": duplicate_profile["total"],
                    },
                    "name_similarity": name_similarity,
                    "structure_similarity": structure_similarity,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
    candidates.sort(key=lambda item: (-float(item["confidence"]), item["canonical_hardware"]["name"]))
    return {"count": len(candidates), "items": candidates}


def _candidate_match(
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    source_parent_name: str,
    target_parent_name: str,
    accepted: Counter[str],
    rejected: Counter[str],
    used_ids: set[str],
) -> tuple[dict[str, Any] | None, float, str, str]:
    ranked: list[tuple[float, dict[str, Any], str, str]] = []
    for candidate in candidates:
        candidate_id = str(candidate["id"])
        if candidate_id in used_ids:
            continue
        key = _learning_key(
            str(source["object_type"]),
            str(source["name"]),
            str(candidate["name"]),
            source_context=source_parent_name,
            target_context=target_parent_name,
        )
        base = semantic_name_similarity(
            source["name"],
            candidate["name"],
            left_context=source_parent_name,
            right_context=target_parent_name,
        )
        context_similarity = semantic_name_similarity(source_parent_name, target_parent_name)
        score = max(0.0, min(1.0, base + min(0.12, accepted[key] * 0.03) - min(0.18, rejected[key] * 0.04)))
        context_conflict = base >= DUPLICATE_THRESHOLD and context_similarity < 0.45
        if context_conflict:
            score = min(score, CONTEXT_CONFLICT_CAP)
            reason = "ähnliche Rollenbezeichnung, aber abweichender fachlicher Elternkontext"
        else:
            reason = "Namensgleich" if str(source["name"]).casefold() == str(candidate["name"]).casefold() else "inhaltlich gleiche technische Logik"
        if accepted[key]:
            reason += f", {accepted[key]} bestätigte Lernbeispiele"
        if rejected[key]:
            reason += f", {rejected[key]} abgelehnte Lernbeispiele"
        ranked.append((round(score, 2), candidate, reason, key))
    if not ranked:
        key = _learning_key(
            str(source["object_type"]),
            str(source["name"]),
            None,
            source_context=source_parent_name,
            target_context=target_parent_name,
        )
        return None, 0.0, "keine vergleichbare Logik vorhanden", key
    score, candidate, reason, key = max(ranked, key=lambda item: item[0])
    return candidate, score, reason, key


def _target_plan(
    source_hardware: dict[str, Any],
    target_hardware: dict[str, Any],
    objects: dict[str, list[dict[str, Any]]],
    by_id: dict[str, dict[str, Any]],
    children: dict[tuple[str, str], list[dict[str, Any]]],
    accepted: Counter[str],
    rejected: Counter[str],
) -> list[dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {
        str(source_hardware["id"]): {
            "target_id": str(target_hardware["id"]),
            "target_name": target_hardware["name"],
            "plan_key": None,
        }
    }
    used_target_ids: set[str] = set()
    plan: list[dict[str, Any]] = []
    for level, object_type in enumerate(TRANSFER_TYPES[1:], start=1):
        parent_field, parent_type, relation_type = PARENT_LINKS[object_type]
        for source in sorted(objects[object_type], key=lambda item: str(item.get("name") or "").lower()):
            source_parent_id = str(source.get(parent_field) or "")
            parent_ref = mapped.get(source_parent_id)
            if not parent_ref:
                continue
            source_parent = by_id.get(source_parent_id, source_hardware)
            target_parent_name = str(parent_ref["target_name"])
            candidates = children.get((object_type, str(parent_ref.get("target_id") or "")), []) if parent_ref.get("target_id") else []
            candidate, similarity, reason, learning_key = _candidate_match(
                source,
                candidates,
                source_parent_name=str(source_parent.get("name") or ""),
                target_parent_name=target_parent_name,
                accepted=accepted,
                rejected=rejected,
                used_ids=used_target_ids,
            )
            recommended_name = adapt_structure_name(
                str(source["name"]),
                str(source_parent.get("name") or ""),
                target_parent_name,
            )
            recommended_name = adapt_structure_name(
                recommended_name,
                str(source_hardware["name"]),
                str(target_hardware["name"]),
            )
            duplicate = candidate is not None and similarity >= DUPLICATE_THRESHOLD
            plan_key = f"{object_type}:{source['id']}"
            target_id = str(candidate["id"]) if duplicate and candidate else None
            target_name = str(candidate["name"]) if duplicate and candidate else recommended_name
            if target_id:
                used_target_ids.add(target_id)
            else:
                learning_key = _learning_key(
                    object_type,
                    str(source["name"]),
                    None,
                    source_context=str(source_parent.get("name") or ""),
                    target_context=target_parent_name,
                )
            confidence = similarity if duplicate else round(max(0.64, 0.88 - similarity * 0.35), 2)
            item = {
                "object_type": object_type,
                "source_id": str(source["id"]),
                "source_name": source["name"],
                "source_parent_id": source_parent_id,
                "source_parent_name": source_parent.get("name"),
                "target_hardware_id": str(target_hardware["id"]),
                "target_parent_type": parent_type,
                "target_parent_id": parent_ref.get("target_id"),
                "target_parent_plan_key": parent_ref.get("plan_key"),
                "target_parent_name": target_parent_name,
                "target_id": target_id,
                "target_name": target_name if duplicate else None,
                "recommended_name": recommended_name,
                "action": "reuse" if duplicate else "create",
                "suggested_action": "reuse" if duplicate else "create",
                "similarity": similarity,
                "confidence": confidence,
                "reason": reason if duplicate else (
                    f"{reason}; als neues Objekt vorgeschlagen"
                    if candidate is not None and similarity > 0
                    else "fehlende Logik wird aus der Referenz-ECU ergänzt"
                ),
                "relation_type": relation_type,
                "parent_field": parent_field,
                "plan_key": plan_key,
                "learning_key": learning_key,
                "level": level,
            }
            plan.append(item)
            mapped[str(source["id"])] = {
                "target_id": target_id,
                "target_name": target_name,
                "plan_key": None if target_id else plan_key,
            }
    return plan


def analyze_ecu_transfer(data: dict[str, Any]) -> dict[str, Any]:
    source_id = str(data.get("source_hardware_id") or "")
    raw_target_ids = data.get("target_hardware_ids")
    if not source_id or not isinstance(raw_target_ids, list):
        raise EngineeringValidationError("source_hardware_id und target_hardware_ids sind Pflichtfelder.")
    target_ids = list(dict.fromkeys(str(value) for value in raw_target_ids if value and str(value) != source_id))
    if not target_ids:
        raise EngineeringValidationError("Mindestens eine andere Ziel-ECU muss ausgewählt sein.")
    if len(target_ids) > 200:
        raise EngineeringValidationError("Es können höchstens 200 Ziel-ECUs gleichzeitig analysiert werden.")

    source_hardware = get_object("HardwareNode", source_id)
    if not _is_ecu(source_hardware):
        raise EngineeringValidationError("Die Referenz-Hardware muss eine ECU sein.")
    targets = [get_object("HardwareNode", target_id) for target_id in target_ids]
    invalid_targets = [target["name"] for target in targets if not _is_ecu(target)]
    if invalid_targets:
        raise EngineeringValidationError(f"Keine ECU: {', '.join(invalid_targets[:5])}.")

    objects, by_id, children = _load_graph()
    accepted, rejected, accepted_count, rejected_count = _reviewed_transfer_examples()
    analyses: list[dict[str, Any]] = []
    for target in targets:
        plan = _target_plan(source_hardware, target, objects, by_id, children, accepted, rejected)
        if not plan:
            raise EngineeringValidationError("Die Referenz-ECU enthält keine übertragbare Funktion.")
        create_count = sum(item["action"] == "create" for item in plan)
        reuse_count = len(plan) - create_count
        confidence = round(sum(float(item["confidence"]) for item in plan) / len(plan), 2)
        proposal = create_proposal(
            {
                "proposal_type": "STRUCTURE_REPLICATION",
                "target_object": {
                    "resource": "structure-tree",
                    "source_hardware_id": source_id,
                    "target_hardware_id": str(target["id"]),
                },
                "prompt": f"Übertrage die Struktur von {source_hardware['name']} auf {target['name']} und vermeide semantische Dubletten.",
                "model": TRANSFER_MODEL,
                "model_version": TRANSFER_MODEL_VERSION,
                "confidence": confidence,
                "retrieved_context": [
                    {"accepted_transfer_reviews": accepted_count},
                    {"rejected_transfer_reviews": rejected_count},
                ],
                "evidence": [
                    {"type": "semantic_name_comparison", "count": len(plan)},
                    {"type": "canonical_hierarchy", "count": len(plan)},
                ],
                "proposed_objects": plan,
                "created_by": data.get("actor") or "structure-transfer-ai",
            }
        )
        analyses.append(
            {
                "proposal_id": str(proposal["proposal_id"]),
                "source_hardware": {"id": source_id, "name": source_hardware["name"]},
                "target_hardware": {"id": str(target["id"]), "name": target["name"]},
                "confidence": confidence,
                "summary": {
                    "total": len(plan),
                    "create": create_count,
                    "reuse": reuse_count,
                    "semantic_duplicates": reuse_count,
                },
                "items": plan,
            }
        )
    return {
        "model": TRANSFER_MODEL,
        "model_version": TRANSFER_MODEL_VERSION,
        "source_hardware": {"id": source_id, "name": source_hardware["name"]},
        "targets": analyses,
        "learning": {
            "accepted": accepted_count,
            "rejected": rejected_count,
            "reviewed": accepted_count + rejected_count,
        },
    }


def _remap_value(value: Any, resolved: dict[str, dict[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _remap_value(item, resolved) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap_value(item, resolved) for item in value]
    if not isinstance(value, str):
        return value
    result = value
    for source_id, target in resolved.items():
        result = result.replace(source_id, target["id"])
        source_name = target.get("source_name")
        if source_name:
            result = re.sub(re.escape(source_name), target["name"], result, flags=re.IGNORECASE)
    return result


def _clone_payload(
    source: dict[str, Any],
    item: dict[str, Any],
    parent: dict[str, str],
    target_hardware_id: str,
    resolved: dict[str, dict[str, str]],
    proposal_id: str,
    actor: str,
) -> dict[str, Any]:
    object_type = str(item["object_type"])
    spec = get_spec(object_type)
    payload = {
        field: _remap_value(source.get(field), resolved)
        for field in (*BASE_COLUMNS, *spec.own_columns)
        if field in source
    }
    payload["name"] = str(item["recommended_name"])
    payload[str(item["parent_field"])] = parent["id"]
    if object_type == "Interface":
        payload["hardware_node_id"] = target_hardware_id
    if object_type == "Signal" and payload.get("display_name") == source.get("name"):
        payload["display_name"] = payload["name"]
    payload.update(
        {
            "source": "ai_generated",
            "provenance": {
                "origin": "structure-transfer",
                "proposal_id": proposal_id,
                "source_object_id": str(source["id"]),
            },
            "confidence": item.get("confidence"),
            "review_state": "reviewed",
            "approval_state": "approved",
            "actor": actor,
            "created_by": actor,
        }
    )
    return payload


def _merge_transfer_decisions(
    items: list[dict[str, Any]],
    decisions: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Apply reviewed per-item actions without allowing unknown plan entries."""

    decision_by_key: dict[str, dict[str, Any]] = {}
    for decision in decisions or []:
        if not isinstance(decision, dict):
            raise EngineeringValidationError("Jede Transferentscheidung muss ein JSON-Objekt sein.")
        plan_key = str(decision.get("plan_key") or "")
        if not plan_key or plan_key in decision_by_key:
            raise EngineeringValidationError("Transferentscheidungen benötigen eindeutige plan_key-Werte.")
        decision_by_key[plan_key] = decision

    known_keys = {str(item.get("plan_key") or "") for item in items}
    unknown_keys = sorted(set(decision_by_key) - known_keys)
    if unknown_keys:
        raise EngineeringValidationError(f"Unbekannte Transferposition: {unknown_keys[0]}.")

    reviewed: list[dict[str, Any]] = []
    for original in items:
        item = dict(original)
        plan_key = str(item.get("plan_key") or "")
        decision = decision_by_key.get(plan_key, {})
        action = str(decision.get("action") or item.get("action") or "create")
        if action not in {"create", "reuse", "skip"}:
            raise EngineeringValidationError(f"Ungültige Entscheidung für {plan_key}: {action!r}.")
        item.setdefault("suggested_action", item.get("action") or "create")
        item["action"] = action
        item["reviewed_by_user"] = bool(decision)
        if action == "create":
            name = str(decision.get("recommended_name") or item.get("recommended_name") or "").strip()
            if not name:
                raise EngineeringValidationError(f"Für {plan_key} fehlt der Name des neuen Objekts.")
            item["recommended_name"] = name
            item["target_id"] = None
            item["target_name"] = None
        elif action == "reuse":
            target_id = str(decision.get("target_id") or item.get("target_id") or "")
            if not target_id:
                raise EngineeringValidationError(f"Für {plan_key} wurde kein vorhandenes Zielobjekt gewählt.")
            item["target_id"] = target_id
        else:
            item["target_id"] = None
            item["target_name"] = None
        reviewed.append(item)
    return reviewed


def apply_ecu_transfer(
    proposal_id: str,
    *,
    actor: str | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal.get("proposal_type") != "STRUCTURE_REPLICATION":
        raise EngineeringValidationError("Der Vorschlag gehört nicht zur ECU-Strukturübertragung.")
    if proposal.get("status") == "REJECTED":
        raise EngineeringValidationError("Ein abgelehnter ECU-Vorschlag kann nicht angewendet werden.")
    if proposal.get("status") == "APPROVED":
        return {
            "proposal": proposal,
            "created": 0,
            "reused": 0,
            "skipped": 0,
            "already_applied": True,
            "items": proposal.get("proposed_objects") or [],
        }

    target_object = proposal.get("target_object") or {}
    source_hardware = get_object("HardwareNode", str(target_object.get("source_hardware_id") or ""))
    target_hardware = get_object("HardwareNode", str(target_object.get("target_hardware_id") or ""))
    reviewer = actor or "structure-transfer-reviewer"
    resolved: dict[str, dict[str, str]] = {
        str(source_hardware["id"]): {
            "id": str(target_hardware["id"]),
            "name": str(target_hardware["name"]),
            "source_name": str(source_hardware["name"]),
        }
    }
    applied_items: list[dict[str, Any]] = []
    used_target_ids: set[str] = set()
    created_count = 0
    reused_count = 0
    skipped_count = 0
    items = sorted(
        _merge_transfer_decisions(
            [dict(item) for item in proposal.get("proposed_objects") or [] if isinstance(item, dict)],
            decisions,
        ),
        key=lambda item: int(item.get("level") or 99),
    )
    for item in items:
        object_type = str(item.get("object_type") or "")
        if object_type not in TRANSFER_TYPES[1:]:
            raise EngineeringValidationError(f"Ungültiger Transfer-Objekttyp: {object_type!r}.")
        source = get_object(object_type, str(item.get("source_id") or ""))
        parent = resolved.get(str(item.get("source_parent_id") or ""))
        if item.get("action") == "skip" or not parent:
            skipped_count += 1
            applied_items.append(
                {
                    **item,
                    "resolved_action": "skip",
                    "proposal_state": "REJECTED",
                    "reason": item.get("reason") if parent else "übersprungen, weil das Ziel-Elternobjekt nicht übernommen wurde",
                }
            )
            continue
        parent_field, _, _ = PARENT_LINKS[object_type]
        candidate = None
        planned_target_id = str(item.get("target_id") or "")
        if item.get("action") == "reuse" and planned_target_id:
            planned = get_object(object_type, planned_target_id)
            if str(planned.get(parent_field) or "") == parent["id"] and planned_target_id not in used_target_ids:
                candidate = planned
        if item.get("action") == "reuse" and candidate is None:
            raise EngineeringValidationError(f"Das gewählte vorhandene Zielobjekt für {source['name']} ist nicht mehr gültig.")
        if candidate is not None:
            target = candidate
            resolved_action = "reuse"
            reused_count += 1
        else:
            target = create_object(
                object_type,
                _clone_payload(
                    source,
                    item,
                    parent,
                    str(target_hardware["id"]),
                    resolved,
                    proposal_id,
                    reviewer,
                ),
            )
            resolved_action = "create"
            created_count += 1
        target_id = str(target["id"])
        used_target_ids.add(target_id)
        resolved[str(source["id"])] = {
            "id": target_id,
            "name": str(target["name"]),
            "source_name": str(source["name"]),
        }
        applied_items.append(
            {
                **item,
                "canonical_id": target_id,
                "target_id": target_id,
                "target_name": target["name"],
                "resolved_action": resolved_action,
                "proposal_state": "APPROVED",
            }
        )

    update_proposal(proposal_id, {"proposed_objects": applied_items, "actor": reviewer})
    proposal = record_proposal_decision(
        proposal_id,
        accepted=True,
        actor=reviewer,
        proposed_objects=applied_items,
    )
    return {
        "proposal": proposal,
        "created": created_count,
        "reused": reused_count,
        "skipped": skipped_count,
        "already_applied": False,
        "items": applied_items,
    }


def reject_ecu_transfer(proposal_id: str, *, actor: str | None = None) -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if proposal.get("proposal_type") != "STRUCTURE_REPLICATION":
        raise EngineeringValidationError("Der Vorschlag gehört nicht zur ECU-Strukturübertragung.")
    if proposal.get("status") == "APPROVED":
        raise EngineeringValidationError("Eine bereits angewendete ECU-Struktur kann nicht abgelehnt werden.")
    return record_proposal_decision(
        proposal_id,
        accepted=False,
        actor=actor or "structure-transfer-reviewer",
    )
