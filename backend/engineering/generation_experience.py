"""Controlled retrieval of reviewed generator decisions.

The service does not train model weights and never turns historic decisions
into current-project approvals.  It exposes compact, reviewed evidence that a
reasoner may use as a suggestion before the deterministic registries decide.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .db import get_connection
from .generation_rule_manager import resolve_generation_policy


MAX_REVIEWED_PROPOSALS = 1000


def _generation_policy(evidence: Any) -> dict[str, Any] | None:
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if not isinstance(item, dict):
            continue
        policy = item.get("generation_policy")
        if isinstance(policy, dict) and policy.get("policy_version"):
            return policy
    return None


def collect_generation_experience(
    rows: Iterable[dict[str, Any]],
    current_policy: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate only human-reviewed proposal outcomes matching the policy."""
    industry_id = (current_policy.get("industry") or {}).get("id")
    requested_buses = {
        str(item.get("id"))
        for item in current_policy.get("bus_types") or []
        if item.get("id")
    }
    aggregates: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = defaultdict(
        lambda: {
            "applied": 0,
            "rejected": 0,
            "proposal_refs": [],
            "generator_sources": [],
        }
    )
    reviewed = 0
    for row in rows:
        contract = row.get("engineering_contract") or {}
        status = str(contract.get("status") or row.get("status") or "").upper()
        if status not in {"APPLIED", "REJECTED"}:
            continue
        policy = _generation_policy(row.get("evidence"))
        if not policy:
            continue
        reviewed += 1
        known_industry = str((policy.get("industry") or {}).get("id") or "")
        known_buses = tuple(sorted(
            str(item.get("id"))
            for item in policy.get("bus_types") or []
            if item.get("id")
        ))
        if industry_id and known_industry != industry_id:
            continue
        if requested_buses and not requested_buses.intersection(known_buses):
            continue
        key = (known_industry, known_buses)
        entry = aggregates[key]
        entry["applied" if status == "APPLIED" else "rejected"] += 1
        reference = str(row.get("proposal_id") or "")
        if reference and len(entry["proposal_refs"]) < 10:
            entry["proposal_refs"].append(reference)
        provenance = policy.get("provenance") or {}
        sources = [
            source
            for item in (provenance.get("technologies") or {}).values()
            for source in item.get("source_modules") or []
        ]
        entry["generator_sources"] = list(dict.fromkeys(
            [*entry["generator_sources"], *sources]
        ))

    suggestions = []
    for (known_industry, known_buses), values in aggregates.items():
        applied = int(values["applied"])
        rejected = int(values["rejected"])
        suggestions.append({
            "industry": known_industry or None,
            "bus_types": list(known_buses),
            "applied": applied,
            "rejected": rejected,
            "confidence": round(applied / max(1, applied + rejected), 3),
            "advisory": True,
            "requires_current_validation": True,
            "proposal_refs": values["proposal_refs"],
            "generator_sources": values["generator_sources"],
        })
    suggestions.sort(
        key=lambda item: (-item["applied"], item["rejected"], item["industry"] or "", item["bus_types"])
    )
    return {
        "reviewed_generation_proposals": reviewed,
        "matching_suggestions": suggestions[:20],
        "learning_mode": "reviewed_retrieval",
        "model_weights_changed": False,
        "authority": "advisory_only",
        "current_policy_sha256": current_policy.get("decision_sha256"),
    }


class GenerationExperienceService:
    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]:
        policy = resolve_generation_policy(
            str(payload.get("prompt") or ""),
            industry=payload.get("industry"),
            bus_types=payload.get("bus_types") or (),
        )
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT proposal_id, project_id, status, engineering_contract, evidence "
                "FROM engineering_ai_proposals ORDER BY modified_at DESC LIMIT %s",
                (MAX_REVIEWED_PROPOSALS,),
            ).fetchall()
        return {
            "generation_policy": policy,
            "experience": collect_generation_experience(rows, policy),
        }
