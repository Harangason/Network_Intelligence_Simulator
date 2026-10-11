"""Canonical behavior persistence used by approved proposals and simulation."""
from __future__ import annotations
from psycopg.types.json import Jsonb
from backend.simulator.signals.core.validation import SUPPORTED_BEHAVIOR_TYPES
from backend.simulator.signals.core.registry import SafeFormula
from .db import get_connection, mark_model_changed
from .project_context import current_project_id
from .repository import get_object


def validate_behavior(data: dict) -> dict:
    signal = get_object("Signal", data["signal_id"])
    if data.get("behavior_type") not in SUPPORTED_BEHAVIOR_TYPES:
        raise ValueError("Unbekanntes Signalverhalten.")
    if data["behavior_type"] == "FORMULA":
        SafeFormula.evaluate(str((data.get("parameters") or {}).get("formula") or ""),{"t":0,"min":0,"max":1,"mid":0.5})
    for dependency in data.get("dependencies") or []:
        get_object("Signal",str(dependency))
        if str(dependency)==str(signal["id"]):
            raise ValueError("Ein Signal darf nicht von sich selbst abhängen.")
    return data


def save_behavior(data: dict) -> dict:
    validate_behavior(data)
    with get_connection() as connection:
        row = connection.execute(
            "INSERT INTO engineering_signal_behaviors (project_id,signal_id,behavior_type,model_label,parameters,dependencies,source) "
            "VALUES (%s,%s,%s,%s,%s,%s,'ai_generated') ON CONFLICT (project_id,signal_id) DO UPDATE SET "
            "behavior_type=excluded.behavior_type,model_label=excluded.model_label,parameters=excluded.parameters,"
            "dependencies=excluded.dependencies,modified_at=now() RETURNING *",
            (current_project_id(),data["signal_id"],data["behavior_type"],data.get("model_label","RULE_BASED"),
             Jsonb(data.get("parameters") or {}),Jsonb(data.get("dependencies") or [])),
        ).fetchone()
    mark_model_changed()
    return {**row,"id":str(row["behavior_id"])}
