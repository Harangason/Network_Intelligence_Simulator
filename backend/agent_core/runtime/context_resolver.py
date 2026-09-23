"""Resolve request context only from server-owned project and conversation state."""
from __future__ import annotations

from typing import Any


class ContextResolver:
    def resolve(self, context: Any, saved_state: dict | None = None) -> dict[str, Any]:
        state = saved_state or {}
        selected = getattr(context, "selected_object_refs", None) or []
        saved_selection = state.get("selected_context") or {}
        if not selected:
            selected = saved_selection.get("selected_object_refs") or []
        workload_id = state.get("active_engineering_workload_id")
        workloads = state.get("engineering_workloads") or {}
        active_workload = workloads.get(workload_id) if workload_id else None
        return {
            "active_project_id": getattr(context, "active_project_id", None),
            "active_view": getattr(context, "active_view", "model"),
            "project_domain": getattr(context, "project_domain", "custom"),
            "selected_object_refs": selected,
            "active_workload": active_workload or {},
            "active_findings": getattr(context, "unresolved_findings", None) or [],
            "answered_questions": getattr(context, "answered_questions", None) or {},
            "current_workload_id": getattr(context, "current_workload", None),
            "current_requirement": state.get("goal_requirement") or state.get("current_requirement", ""),
            "model_revision": state.get("model_revision"),
            "pending_decisions": [q for q in (state.get("questions") or {}).values() if q.get("status") == "OPEN"],
        }
