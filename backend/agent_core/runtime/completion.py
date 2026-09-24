"""Do not treat a tool response or a navigation action as goal completion."""
from __future__ import annotations


class CompletionEvaluator:
    TERMINAL_COMPLETE = {"COMPLETE", "COMPLETED"}

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
