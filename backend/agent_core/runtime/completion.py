"""Do not treat a tool response or a navigation action as goal completion."""
from __future__ import annotations


class CompletionEvaluator:
    TERMINAL_COMPLETE = {"COMPLETE", "COMPLETED"}

    def evaluate_configuration_apply(self, goal: dict, capacity: dict, preflight: dict,
                                     *, evidence_refs: list[str]) -> dict:
        """Evaluate a verified mutation separately from its dependent analyses.

        A reported deadline violation is a calculation result. Missing routes or
        unverified timing are not. Running preflight does not grant simulation
        permission, so a BLOCKED preflight can still satisfy preflight_rerun.
        """
        results = capacity.get("results") or {}
        networks, routes = results.get("networks") or [], results.get("routes") or []
        source_ready = (bool(networks) and bool(routes)
                        and not capacity.get("is_outdated")
                        and capacity.get("status") not in {"OUTDATED", "STALE"}
                        and not any(item.get("code") in {"CAPACITY_SOURCE_NOT_READY", "CAPACITY_NO_ROUTES"}
                                    for item in capacity.get("findings") or []))
        capacity_id = capacity.get("snapshot_id") or capacity.get("id")
        supported = {
            "configuration_persisted": True,  # caller verified the canonical value
            "capacity_recalculated": bool(capacity_id) and source_ready
                and all(item.get("capacity_verified") is True for item in networks),
            "timing_recalculated": bool(capacity_id) and source_ready
                and all(item.get("timing_verified") is True for item in networks)
                and all(item.get("timing_verified") is True for item in routes),
            "preflight_rerun": bool(preflight.get("snapshot_id")) and bool(capacity_id)
                and preflight.get("capacity_snapshot_id") == capacity_id
                and preflight.get("preflight_status") in {"READY", "READY_WITH_WARNINGS", "REVIEW_REQUIRED", "BLOCKED"},
        }
        required = goal.get("required_outcomes") or list(supported)
        achieved = [name for name in required if supported.get(name)]
        missing = [name for name in required if not supported.get(name)]
        decision = {"status": "BLOCKED_WITH_EXPLICIT_CAUSE" if missing else "COMPLETED",
                    "completed": not missing, "achieved_outcomes": achieved,
                    "missing_outcomes": missing, "evidence_refs": evidence_refs}
        if missing:
            decision["failure"] = {
                "code": "DEPENDENT_CALCULATION_INCOMPLETE",
                "message": "Die Bitrate wurde übernommen. Abhängige Berechnungen sind noch nicht vollständig nachgewiesen.",
                "missing_outcomes": missing,
                "capacity_findings": capacity.get("findings") or [],
                "preflight_findings": preflight.get("findings") or [],
            }
        return decision

    def evaluate(self, goal: dict, events: list[dict], *, failure: dict | None = None) -> dict:
        failure = failure or next((event.get('metadata', {}).get('failure') for event in reversed(events)
                                   if event.get('metadata', {}).get('failure')), None)
        if failure:
            return {"status": "BLOCKED_WITH_EXPLICIT_CAUSE", "completed": False,
                    "missing_outcomes": list(goal.get("required_outcomes") or []), "failure": failure}
        question = next((event for event in reversed(events) if event.get("type") in {"QUESTION", "SINGLE_SELECT", "MULTI_SELECT"}), None)
        approval = next((event for event in reversed(events) if event.get("type") == "APPROVAL"), None)
        result = next((event for event in reversed(events) if event.get("type") == "RESULT"), None)
        if question and (not result or question.get("created_at", "") >= result.get("created_at", "")):
            status = "WAITING_FOR_ENGINEERING_DECISION"
        elif approval:
            status = "READY_FOR_REVIEW"
        elif not result:
            status = "INCOMPLETE"
        elif result.get("status") in self.TERMINAL_COMPLETE:
            details = (result.get("metadata") or {}).get("details")
            completion = details.get("completion") if isinstance(details, dict) else None
            outputs = result.get("outputs") or []
            if isinstance(completion, dict) and completion.get("complete") is True:
                status = "COMPLETED"
            elif outputs and all(isinstance(item, dict) and item.get("evidence_refs") for item in outputs):
                status = "COMPLETED"
            else:
                # A successful operation or optimistic assistant status is not
                # sufficient evidence that the requested engineering goal holds.
                status = "INCOMPLETE"
        elif goal.get("goal_type") in {"STATUS_QUERY", "EXPLAIN", "DIAGNOSE", "ANALYZE_TRACE", "MEASURE_E2E", "VALIDATE_MODEL", "CALCULATE_CAPACITY", "CALCULATE_TIMING", "COMPARE"} and result.get("status") in {"ANSWERED", "SUCCESS", "PASS"}:
            # Read-only analysis goals complete only with a final structured result.
            status = "COMPLETED" if result.get("metadata", {}).get("details") is not None or result.get("metadata", {}).get("evidence_refs") else "INCOMPLETE"
        elif result.get("status") == 'WAITING_FOR_ENGINEERING_DECISION':
            status = 'WAITING_FOR_ENGINEERING_DECISION'
        elif result.get("status") in {"NOT_SUPPORTED", "NOT_SUPPORTED_WITH_CAPABILITY_GAP"}:
            status = "NOT_SUPPORTED_WITH_CAPABILITY_GAP"
        elif result.get("status") in {"BLOCKED", "FAILED", "ERROR", "INCOMPLETE", "OPEN"}:
            status = "BLOCKED_WITH_EXPLICIT_CAUSE" if result.get("text") else "INCOMPLETE"
        else:
            status = "INCOMPLETE"
        achieved = []
        if status == "COMPLETED":
            achieved = list(goal.get("required_outcomes") or [])
        return {"status": status, "completed": status == "COMPLETED",
                "achieved_outcomes": achieved,
                "missing_outcomes": [] if status == "COMPLETED" else list(goal.get("required_outcomes") or []),
                "evidence_refs": [str(item.get("metadata", {}).get("input_ref") or item.get("id")) for item in events
                                  if item.get("type") in {"RESULT", "APPROVAL", "FINDING"}]}
