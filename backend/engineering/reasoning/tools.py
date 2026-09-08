"""MCP adapters for the single Python reasoning service."""
from typing import Any
from pydantic import Field
from backend.agent_core.api.tool_contract import ToolResult, ToolStatus, Permission
from ..agent_tools.catalog import register, ID
from .contracts import ReasoningRequest
from .service import ReasoningService


def result_contract(result):
    complete = result.completion_status in {"COMPLETE", "NO_ANOMALY_IN_WINDOW"} and result.validation_status == "CURRENT"
    return ToolResult(success=True, status=ToolStatus.SUCCESS if complete else ToolStatus.PARTIAL,
        data=result.model_dump(mode="json"), evidence_refs=[e.model_dump(mode="json") for e in result.evidence_refs],
        warnings=[g["message"] for g in result.data_gaps], findings=result.findings,
        time_range=result.time_range, validation_status=result.validation_status,
        affected_objects=[dict(pair) for pair in dict.fromkeys(tuple(sorted(obj.items())) for o in result.observations for obj in o.affected_objects)])


def analyze(arguments):
    return result_contract(ReasoningService().analyze({k: v for k, v in arguments.items() if k in ReasoningRequest.model_fields}))


def inspect(name, arguments):
    data = ReasoningService().inspect(name, arguments)
    return ToolResult(success=True, status=ToolStatus.PARTIAL if data["validation_status"] == "PARTIAL" else ToolStatus.SUCCESS,
                      **data)


def register_reasoning_tools():
    fields = dict(job_id=ID, goal=(str, Field(default="Ursache im Trace untersuchen.", max_length=2000)),
        focus_s=(float | None, Field(default=None, ge=0)), start_s=(float, Field(default=0, ge=0)),
        end_s=(float, Field(default=1e15, ge=0)), cursor=(int, Field(default=0, ge=0)),
        golden_job_id=(str | None, None))
    for name in ("analyze_trace_root_cause", "explain_simulation_failure", "investigate_deadline_miss", "analyze_fault_effects"):
        register(name, "Strukturierte Ursachenanalyse mit Evidenz, Hypothesen und separater Completion-Prüfung; keine Modelländerung.", Permission.ANALYZE_TRACE, analyze, **fields)
    for name in ("get_trace_events", "get_signal_series", "get_fault_events", "get_state_transitions", "get_route", "get_network_load", "get_timing_metrics", "find_first_divergence", "correlate_events"):
        register(name, "Begrenzte, projektgebundene Trace-Evidenz über bestehende Python-Fachdienste abrufen.", Permission.ANALYZE_TRACE,
                 lambda a, n=name: inspect(n, a), **fields, signal_id=(str | None, None))
    register("continue_reasoning", "Offene Evidenzabfrage begrenzt fortsetzen; Erfolg ist nicht Ursachenbestätigung.", Permission.ANALYZE_TRACE,
             lambda a: result_contract(ReasoningService().continue_analysis(a["reasoning_id"])), reasoning_id=ID)
    register("inspect_reasoning", "Persistierte Evidenz und Aktualität einer Analyse lesen.", Permission.READ_MODEL,
             lambda a: result_contract(ReasoningService().get(a["reasoning_id"])), reasoning_id=ID)
    register("compare_simulation_runs", "Zwei persistierte Ursachenanalysen bei vergleichbarem Szenario, Seed und Zeitfenster vergleichen.", Permission.ANALYZE_TRACE,
             lambda a: ReasoningService().compare_runs(a["before_reasoning_id"], a["after_reasoning_id"]), before_reasoning_id=ID, after_reasoning_id=ID)
    register("create_reasoning_proposal", "Eine aktuelle Empfehlung mit dem bestehenden Planer in einen menschlich zu prüfenden Vorschlag überführen.", Permission.GENERATE_PROPOSAL,
             lambda a: ReasoningService().propose(a["reasoning_id"], a["action_id"]), reasoning_id=ID, action_id=ID)
