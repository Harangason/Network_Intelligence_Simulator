"""Canonical behavior persistence used by approved proposals and simulation."""
from __future__ import annotations
from psycopg.types.json import Jsonb
from backend.nis.simulation.signals.core.validation import SUPPORTED_BEHAVIOR_TYPES
from backend.nis.simulation.signals.core.registry import SafeFormula
from backend.nis.infrastructure.persistence.db import get_connection
from backend.nis.infrastructure.persistence.db import mark_model_changed
from backend.nis.engineering.projects.project_context import current_project_id
from backend.nis.infrastructure.persistence.repository import get_object


def validate_behavior(data: dict) -> dict:
    signal = get_object("Signal", data["signal_id"])
    if data.get("behavior_type") not in SUPPORTED_BEHAVIOR_TYPES:
        raise ValueError("Unbekanntes Signalverhalten.")
    if data["behavior_type"] == "FORMULA":
        SafeFormula.evaluate(str((data.get("parameters") or {}).get("formula") or ""),{"t":0,"min":0,"max":1,"mid":0.5})
    if data['behavior_type'] == 'FUNCTION_BLOCK':
        from backend.nis.agent.tools.model import ProjectRepository
        from backend.nis.simulation.signals.core.function_block import validate_function_spec
        repository = ProjectRepository()
        context = repository.function_context(data['signal_id'])
        parameters = data.get('parameters') or {}
        if not (parameters.get('function_block') or {}).get('verification_cases'):
            raise ValueError('Executable function proposals require independent expected-value cases.')
        bindings = parameters.get('transport_inputs') or {}
        sources = {str(policy['signal_id']): repository.get('Signal', policy['signal_id']) for policy in bindings.values()}
        validate_function_spec(parameters, sources)
        if set(data.get('dependencies') or []) != set(sources):
            raise ValueError('Declared function dependencies differ from the input bindings.')
        received = {str(row['id']) for row in context['candidate_inputs']}
        if set(sources) - received:
            raise ValueError('Function input has no declared route/consumer binding to this ECU.')
        for value in (parameters['invalid_output'],):
            if not float(signal.get('min_value', 0)) <= float(value) <= float(signal.get('max_value', 1)):
                raise ValueError('Invalid-input output lies outside its canonical signal range.')
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
        if data['behavior_type'] == 'FUNCTION_BLOCK':
            from backend.nis.infrastructure.storage.saved_storage import ProjectArtifactStore
            ProjectArtifactStore(current_project_id()).stage_block(data['parameters']['function_block'])
    mark_model_changed()
    return {**row,"id":str(row["behavior_id"])}
