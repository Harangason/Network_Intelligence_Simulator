"""Reuse project review evidence without inheriting approvals or hiding failures."""

from typing import Any


def enrich_with_review_history(recommendations: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> dict[str, int]:
    reviewed = [item for item in proposals if item.get("status") in {"ACCEPTED", "REJECTED", "APPLIED_AS_DRAFT"}]
    matched = 0
    for recommendation in recommendations:
        affected = set(map(str, recommendation.get("affected_objects") or []))
        history = []
        for proposal in reviewed:
            if proposal.get("category") != recommendation.get("category"):
                continue
            same_problem = proposal.get("problem") == recommendation.get("problem")
            same_objects = affected and affected == set(map(str, proposal.get("affected_objects") or []))
            if not (same_problem or same_objects):
                continue
            history.append({
                "proposal_id": str(proposal["proposal_id"]), "status": proposal["status"],
                "reason": proposal.get("review_reason"), "reviewed_by": proposal.get("reviewed_by"),
                "previous_recommendation": proposal.get("recommendation"),
                "source_snapshot_id": str(proposal.get("source_snapshot_id") or ""),
                "updated_at": str(proposal.get("updated_at") or ""),
            })
        history.sort(key=lambda item: item["updated_at"], reverse=True)
        if history:
            recommendation["review_history"] = history[:5]
            recommendation["requires_fresh_review"] = True
            matched += 1
    return {"reviewed_proposals": len(reviewed), "matched_recommendations": matched}
