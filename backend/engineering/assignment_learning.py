"""Project-spanning retrieval and persistence for reviewed equipment ownership."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .models import EngineeringValidationError

MAX_FEEDBACK_RECORDS = 2000
MAX_HISTORY_PROJECTS = 500


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.replace("ß", "ss")
    text = re.sub(r"(?:[-_ ]+\d+)+$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _wizard_assignments(context: dict[str, Any]) -> list[dict[str, Any]]:
    wizard = context.get("agent_wizard_status")
    if not isinstance(wizard, dict):
        return []
    assignments = wizard.get("system_cluster_assignments")
    return assignments if isinstance(assignments, list) else []


def _historical_records(project_id: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    explicit = context.get("equipment_assignment_feedback")
    if isinstance(explicit, list):
        for record in explicit:
            if isinstance(record, dict):
                records.append({**record, "project_id": project_id, "weight": 4 if record.get("accepted", True) else -6})
    for assignment in _wizard_assignments(context):
        if not isinstance(assignment, dict) or assignment.get("selected") is False:
            continue
        for controller in assignment.get("tree") or []:
            if not isinstance(controller, dict) or not controller.get("name"):
                continue
            for device_type, key in (("SensorController", "sensors"), ("ActuatorController", "actuators")):
                for endpoint in controller.get(key) or []:
                    endpoint_name = endpoint.get("name") if isinstance(endpoint, dict) else endpoint
                    if endpoint_name:
                        records.append({
                            "endpoint_name": endpoint_name,
                            "controller_name": controller["name"],
                            "device_type": device_type,
                            "accepted": True,
                            "project_id": project_id,
                            "source": "wizard-submission",
                            "weight": 1,
                        })
    return records


def collect_assignment_suggestions(
    project_rows: list[dict[str, Any]],
    endpoints: list[dict[str, Any]],
    candidate_controllers: list[str],
    domain: str = "",
) -> dict[str, Any]:
    """Rank exact reviewed endpoint/controller evidence for the current graph."""
    candidate_by_key = {_normalized(name): name for name in candidate_controllers if _normalized(name)}
    scores: dict[tuple[str, str], int] = defaultdict(int)
    evidence_counts: dict[tuple[str, str], int] = defaultdict(int)
    projects: dict[tuple[str, str], set[str]] = defaultdict(set)
    corpus_projects = 0
    for row in project_rows:
        context = row.get("context") or {}
        if not isinstance(context, dict):
            continue
        records = _historical_records(str(row.get("project_id") or ""), context)
        if records:
            corpus_projects += 1
        for record in records:
            record_domain = _normalized(record.get("domain"))
            if domain and record_domain and record_domain != _normalized(domain):
                continue
            endpoint_key = _normalized(record.get("endpoint_name"))
            controller_key = _normalized(record.get("controller_name"))
            if not endpoint_key or controller_key not in candidate_by_key:
                continue
            key = (endpoint_key, controller_key)
            scores[key] += int(record.get("weight") or 0)
            evidence_counts[key] += 1
            projects[key].add(str(record.get("project_id") or ""))

    suggestions: list[dict[str, Any]] = []
    for endpoint in endpoints:
        endpoint_name = str(endpoint.get("name") or "").strip()
        endpoint_key = _normalized(endpoint_name)
        ranked = sorted(
            ((score, controller_key) for (known_endpoint, controller_key), score in scores.items() if known_endpoint == endpoint_key),
            reverse=True,
        )
        if not ranked or ranked[0][0] <= 0:
            continue
        score, controller_key = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else 0
        if score <= runner_up:
            continue
        evidence_key = (endpoint_key, controller_key)
        suggestions.append({
            "endpoint_name": endpoint_name,
            "controller_name": candidate_by_key[controller_key],
            "confidence": min(0.99, 0.82 + min(score, 12) * 0.0125),
            "reason": "Projektübergreifend bestätigte Controller-Zuordnung (RAG).",
            "evidence_count": evidence_counts[evidence_key],
            "source_projects": sorted(project for project in projects[evidence_key] if project),
            "retrieval_sources": ["wizard-review-history", "system-cluster-graph"],
        })
    return {"suggestions": suggestions, "corpus_projects": corpus_projects}


class EquipmentAssignmentLearningService:
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id

    def retrieve(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoints = payload.get("endpoints") or []
        controllers = payload.get("candidate_controllers") or []
        if not isinstance(endpoints, list) or not isinstance(controllers, list):
            raise EngineeringValidationError("endpoints und candidate_controllers müssen Listen sein.")
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT project_id, context FROM engineering_workflow_projects ORDER BY updated_at DESC LIMIT %s",
                (MAX_HISTORY_PROJECTS,),
            ).fetchall()
        return {
            **collect_assignment_suggestions(rows, endpoints, [str(value) for value in controllers], str(payload.get("domain") or "")),
            "project_id": self.project_id,
        }

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        records = payload.get("records") or []
        if not isinstance(records, list) or not records:
            raise EngineeringValidationError("records muss eine nicht-leere Liste sein.")
        cleaned: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            endpoint_name = str(record.get("endpoint_name") or "").strip()
            controller_name = str(record.get("controller_name") or "").strip()
            if not endpoint_name or not controller_name:
                continue
            cleaned.append({
                "endpoint_name": endpoint_name,
                "controller_name": controller_name,
                "device_type": str(record.get("device_type") or ""),
                "domain": str(record.get("domain") or payload.get("domain") or ""),
                "accepted": bool(record.get("accepted", True)),
                "source": str(record.get("source") or payload.get("source") or "wizard-review"),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            })
        if not cleaned:
            raise EngineeringValidationError("Keine gültige Gerätezuordnung übergeben.")
        with get_connection() as connection:
            connection.execute("INSERT INTO engineering_workflow_projects (project_id) VALUES (%s) ON CONFLICT DO NOTHING", (self.project_id,))
            row = connection.execute(
                "SELECT context FROM engineering_workflow_projects WHERE project_id = %s FOR UPDATE",
                (self.project_id,),
            ).fetchone()
            context = dict((row or {}).get("context") or {})
            history = list(context.get("equipment_assignment_feedback") or [])
            history.extend(cleaned)
            context["equipment_assignment_feedback"] = history[-MAX_FEEDBACK_RECORDS:]
            connection.execute(
                "UPDATE engineering_workflow_projects SET context = %s, updated_at = now() WHERE project_id = %s",
                (Jsonb(context), self.project_id),
            )
        return {"project_id": self.project_id, "recorded": len(cleaned), "stored": len(context["equipment_assignment_feedback"])}
