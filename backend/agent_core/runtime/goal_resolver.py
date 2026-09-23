"""Deterministically turn user wording and saved follow-up context into a goal."""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class GoalType(StrEnum):
    CREATE_PROJECT = "CREATE_PROJECT"
    CREATE_HARDWARE = "CREATE_HARDWARE"
    CREATE_FUNCTION = "CREATE_FUNCTION"
    CREATE_SIGNAL = "CREATE_SIGNAL"
    CREATE_NETWORK = "CREATE_NETWORK"
    CONNECT_OBJECTS = "CONNECT_OBJECTS"
    CHANGE_CONFIGURATION = "CHANGE_CONFIGURATION"
    VALIDATE_MODEL = "VALIDATE_MODEL"
    CALCULATE_CAPACITY = "CALCULATE_CAPACITY"
    CALCULATE_TIMING = "CALCULATE_TIMING"
    RUN_SIMULATION = "RUN_SIMULATION"
    ANALYZE_TRACE = "ANALYZE_TRACE"
    MEASURE_E2E = "MEASURE_E2E"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    OPTIMIZE = "OPTIMIZE"
    EXPLAIN = "EXPLAIN"
    COMPARE = "COMPARE"
    REMOVE = "REMOVE"
    PERIODIC_ACQUISITION = "PERIODIC_ACQUISITION"
    STATUS_QUERY = "STATUS_QUERY"
    GENERAL_ENGINEERING = "GENERAL_ENGINEERING"


class EngineeringGoal(BaseModel):
    """A compact durable workload description; it never grants mutation rights."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    goal_id: str = Field(default_factory=lambda: str(uuid4()))
    goal_type: GoalType
    original_request: str = Field(min_length=1, max_length=200000)
    project_context: dict[str, Any] = Field(default_factory=dict)
    requested_objects: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)
    requested_changes: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)
    timing_constraints: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)
    technology_constraints: list[str] = Field(default_factory=list, max_length=20)
    target_objects: list[dict[str, str]] = Field(default_factory=list, max_length=2000)
    user_constraints: list[str] = Field(default_factory=list, max_length=2000)
    required_outcomes: list[str] = Field(default_factory=list, max_length=30)
    unresolved_decisions: list[str] = Field(default_factory=list, max_length=30)
    follow_up_of: str | None = None


_ACTION = re.compile(
    r"\b(?:erstelle|erstell\w*|erzeuge|erzeug\w*|anleg\w*|führe\w*|fuehre\w*|"
    r"lege\b.{0,120}\ban\b|"
    r"füge\w*\s+hinzu|fuege\w*\s+hinzu|verbinde|ändere|aendere|konfigurier\w*|"
    r"entferne|lösche|loesche|prüfe|pruefe|validier\w*|berechne|simulier\w*|"
    r"analysier\w*|diagnostizier\w*|reparier\w*|beheb\w*|optimi\w*|erklär\w*|"
    r"vergleiche|zeige|status|create|add|connect|change|configure|remove|delete|"
    r"validate|calculate|simulate|analy[sz]e|diagnose|repair|fix|optimi[sz]e|explain|compare|execute|run)\b",
    re.I,
)


def _timing(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in re.finditer(r"\b(?:alle\s+)?(\d+(?:[.,]\d+)?)\s*(ms|msec|s|sek(?:unden?)?|min(?:uten?)?)\b", text, re.I):
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).casefold()
        seconds = value / 1000 if unit in {"ms", "msec"} else value * 60 if unit.startswith("min") else value
        result.append({"kind": "PERIOD", "value": value, "unit": match.group(2), "seconds": seconds})
    return result


def _requested_objects(text: str) -> list[dict[str, Any]]:
    patterns = (
        ("CONTROLLER", r"\b(?:controller|steuergerät|steuergeraet|plc)\b"),
        ("PRESSURE_SENSOR", r"\b(?:drucksensor|pressure\s+sensor)\b"),
        ("SENSOR", r"\b(?:sensor|messfühler|messfuehler)\b"),
        ("VALVE_ACTUATOR", r"\b(?:ventil(?:aktor)?|valve\s+actuator)\b"),
        ("ACTUATOR", r"\b(?:aktor|actuator|stellglied)\b"),
        ("SIGNAL", r"\b(?:signal|signale)\b"),
        ("NETWORK", r"\b(?:netzwerk|netz|network|bus)\b"),
        ("ECU", r"\becu\b"),
    )
    found: list[dict[str, Any]] = []
    for kind, pattern in patterns:
        matches = list(re.finditer(pattern, text, re.I))
        if not matches:
            continue
        for match in matches:
            before = text[max(0, match.start() - 24):match.start()]
            count_match = re.search(r"(\d+)\s*$", before)
            found.append({"type": kind, "count": int(count_match.group(1)) if count_match else 1,
                          "source_span": [match.start(), match.end()]})
    # Prefer the more specific pressure-sensor/valve-actuator forms and avoid
    # counting the same mention again as a generic sensor/actuator.
    specific_spans = {(item["source_span"][0], item["source_span"][1]) for item in found
                      if item["type"] in {"PRESSURE_SENSOR", "VALVE_ACTUATOR"}}
    result = []
    for item in found:
        if item["type"] == "SENSOR" and any(a <= item["source_span"][0] <= b for a, b in specific_spans):
            continue
        if item["type"] == "ACTUATOR" and any(a <= item["source_span"][0] <= b for a, b in specific_spans):
            continue
        if item not in result:
            result.append(item)
    return result


def _technologies(text: str) -> list[str]:
    aliases = {"can-fd": "CAN_FD", "can fd": "CAN_FD", "can": "CAN", "lin": "LIN",
               "i2c": "I2C", "spi": "SPI", "uart": "UART", "ethernet": "ETHERNET",
               "modbus rtu": "MODBUS_RTU", "modbus": "MODBUS", "profinet": "PROFINET",
               "ethercat": "ETHERCAT", "flexray": "FLEXRAY"}
    found: list[str] = []
    for alias, technology in sorted(aliases.items(), key=lambda item: -len(item[0])):
        for match in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I):
            before = text[max(0, match.start() - 32):match.start()]
            after = text[match.end():match.end() + 28]
            if re.search(r"\b(?:nicht|kein|keine|ohne|statt|rather than|instead of|not|no|except)\s+(?:\w+\s+){0,2}$", before, re.I):
                continue
            if re.match(r"\s*(?:nicht|kein|keine|not\s+(?:used|required)|isn't\s+used)\b", after, re.I):
                continue
            if technology not in found:
                found.append(technology)
    return found


_OUTCOMES: dict[GoalType, list[str]] = {
    GoalType.CREATE_PROJECT: ["canonical_objects_resolved", "proposal_validated", "model_change_reviewed"],
    GoalType.CREATE_HARDWARE: ["hardware_exists", "hardware_classified", "model_validated"],
    GoalType.CREATE_FUNCTION: ["function_exists", "hardware_mapping_valid", "model_validated"],
    GoalType.CREATE_SIGNAL: ["signal_exists", "encoding_preserved", "signal_validated"],
    GoalType.CREATE_NETWORK: ["network_exists", "technology_resolved", "preflight_valid"],
    GoalType.CONNECT_OBJECTS: ["endpoints_resolved", "route_valid", "capacity_evaluated", "timing_evaluated", "preflight_valid"],
    GoalType.PERIODIC_ACQUISITION: ["requester_exists", "data_sources_resolved", "period_configured", "route_valid", "capacity_evaluated", "timing_evaluated", "preflight_valid"],
    GoalType.CALCULATE_CAPACITY: ["capacity_calculation_current", "findings_reported"],
    GoalType.CALCULATE_TIMING: ["timing_calculation_current", "findings_reported"],
    GoalType.RUN_SIMULATION: ["preflight_valid", "simulation_complete", "scope_evidence_present"],
    GoalType.ANALYZE_TRACE: ["trace_identity_valid", "analysis_complete", "evidence_current"],
    GoalType.MEASURE_E2E: ["e2e_transactions_correlated", "timing_evaluated", "findings_reported"],
    GoalType.DIAGNOSE: ["evidence_inspected", "cause_and_limits_reported"],
    GoalType.REPAIR: ["repair_scope_resolved", "proposal_validated", "revalidation_complete"],
    GoalType.VALIDATE_MODEL: ["validation_current", "findings_reported"],
    GoalType.STATUS_QUERY: ["current_model_status_reported", "metrics_with_units_and_provenance"],
}

# A durable wizard target identifies the stage the user accepted. Prompt text
# often contains requirements for every stage, so lexical matches in that text
# must not redirect the runtime to an unrelated capability.
_WIZARD_TARGET_GOALS: dict[str, GoalType] = {
    "engineering_model": GoalType.CREATE_PROJECT,
    "routing": GoalType.CONNECT_OBJECTS,
    "network_editor": GoalType.CREATE_NETWORK,
    "parameters": GoalType.CHANGE_CONFIGURATION,
    "capacity_timing": GoalType.CALCULATE_CAPACITY,
    "validation": GoalType.VALIDATE_MODEL,
    "simulation": GoalType.RUN_SIMULATION,
    "results_analysis": GoalType.ANALYZE_TRACE,
    "data_science_intelligence": GoalType.GENERAL_ENGINEERING,
}


class GoalResolver:
    """Resolve common engineering requests without making engineering decisions."""

    def resolve(self, prompt: str, context: dict[str, Any] | None = None,
                active_workload: dict[str, Any] | None = None) -> EngineeringGoal:
        source = prompt.strip()
        text = source.casefold()
        context = context or {}
        previous = active_workload or {}
        asked = _ACTION.search(source) is not None
        question = bool(re.match(r"\s*(?:wie|was|welche|warum|wieso|ist|sind|zeige|erkläre|erklaere|kann|how|what|which|why|show|explain|is|are)\b", text))
        wizard_request = context.get("wizard_request")
        wizard_target = (wizard_request.get("target") if isinstance(wizard_request, dict)
                         and wizard_request.get("version") == 2 else None)
        if wizard_target in _WIZARD_TARGET_GOALS:
            kind = _WIZARD_TARGET_GOALS[wizard_target]
        else:
            kind = None
        periodic = bool(re.search(r"\b(?:alle\s+)?\d+(?:[.,]\d+)?\s*(?:s|sek(?:unden?)?|ms|min(?:uten?)?)\b", text)
                        and re.search(r"\b(?:abfrag|abfrage|poll|erfass|erhebung|acquisition|sample)\w*\b", text))
        if kind is not None:
            pass
        elif periodic and re.search(r"\b(?:ecu|controller|steuergerät|steuergeraet|plc)\b", text):
            kind = GoalType.PERIODIC_ACQUISITION
        elif re.search(r"\b(?:trace|trace-session|golden\s+trace)\b", text) and re.search(r"\b(?:analys|untersuch|compare|vergleich|ursach|root)\w*\b", text):
            kind = GoalType.ANALYZE_TRACE
        elif re.search(r"\b(?:end.?to.?end|e2e|ende\s+zu\s+ende)\b", text) and re.search(r"\b(?:mess|prüf|pruef|analys|measure|check)\w*\b", text):
            kind = GoalType.MEASURE_E2E
        elif re.search(r"\b(?:simulation|simulier|simuliere|simulate|lauf starten)\b", text):
            kind = GoalType.RUN_SIMULATION
        elif re.search(r"\b(?:kapazität|kapazitaet|buslast|auslastung|capacity|load)\b", text) and (question or re.search(r"berechn|prüf|pruef|calculate", text)):
            kind = GoalType.CALCULATE_CAPACITY
        elif re.search(r"\b(?:timing|latenz|frist|zykluszeit|jitter|deadline)\b", text) and re.search(r"prüf|pruef|berechn|calculate|warum|why|spät|spaet|late", text):
            kind = GoalType.CALCULATE_TIMING if asked else GoalType.DIAGNOSE
        elif re.search(r"\b(?:status|systemstatus|nis[- ]?status|stand|fortschritt|readiness|bereitschaft|temperatur|temperaturen|cpu|speicher|k\s*(?:und|/)\s*p)\b", text) and not re.search(r"\b(?:erzeug|erstell|anleg|lege|änder|aender|lösch|loesch|verbinde|create|add|update|delete)\w*\b", text):
            kind = GoalType.STATUS_QUERY
        elif re.search(r"\b(?:reparier|beheb|korrigier|fix|repair|fehleranalyse|fehler\s+beheben|restlichen\s+fehler)\w*\b", text):
            kind = GoalType.REPAIR
        elif question and re.search(r"\b(?:warum|wieso|weshalb|ursach|late|zu spät|zu spaet|root cause)\b", text):
            kind = GoalType.DIAGNOSE
        elif re.search(r"\b(?:vergleich|vergleiche|compare|gegenüber|gegenueber)\b", text):
            kind = GoalType.COMPARE
        elif re.search(r"\b(?:optimier|optimize)\w*\b", text):
            kind = GoalType.OPTIMIZE
        elif re.search(r"\b(?:entfern|lösche|loesche|delete|remove)\w*\b", text):
            kind = GoalType.REMOVE
        elif re.search(r"\b(?:validier|prüf|pruef|preflight|validate)\w*\b", text):
            kind = GoalType.VALIDATE_MODEL
        elif re.search(r"\b(?:signal|signals)\b", text) and re.search(r"\b(?:anleg|erstell|erzeug|create|add|hinzufüg|hinzufueg)\w*\b|\blege\b.{0,40}\ban\b", text):
            kind = GoalType.CREATE_SIGNAL
        elif re.search(r"\b(?:netz|network|bus)\b", text) and re.search(r"\b(?:anleg|erstell|erzeug|create|add)\w*\b|\blege\b.{0,40}\ban\b", text):
            kind = GoalType.CREATE_NETWORK
        elif re.search(r"\b(?:funktion|function)\b", text) and asked:
            kind = GoalType.CREATE_FUNCTION
        elif re.search(r"\b(?:projekt|project)\b", text) and asked:
            kind = GoalType.CREATE_PROJECT
        elif re.search(r"\b(?:ecu|controller|steuergerät|steuergeraet|plc|hardware|aktor|actuator|sensor|ventil)\b", text) and asked:
            kind = GoalType.CREATE_HARDWARE
        elif re.search(r"\b(?:verbinde|verbinden|connect|route|routing)\b", text):
            kind = GoalType.CONNECT_OBJECTS
        elif re.search(r"\b(?:ändern|aendern|ändere|aendere|konfigurier|change|configure|rate|bitrate|baudrate)\b", text):
            kind = GoalType.CHANGE_CONFIGURATION
        elif question or not asked:
            kind = GoalType.EXPLAIN
        elif asked and re.search(r"\b(?:anleg|erstell|erzeuge|create|build)\w*\b", text):
            kind = GoalType.CREATE_PROJECT
        else:
            kind = GoalType.GENERAL_ENGINEERING

        follow_up = bool(re.search(r"\b(?:das|dies|dasselbe|auch für|auch fuer|weitere|restlichen|noch einmal|same|that|those|other)\b", text))
        previous_goal = previous.get("goal") if isinstance(previous.get("goal"), dict) else {}
        follow_up_of = previous.get("workload_id") if follow_up and previous_goal else None
        goal_id = str(previous_goal.get("goal_id")) if previous_goal and previous_goal.get("original_request") == source else str(uuid4())
        if follow_up and previous_goal and kind in {GoalType.EXPLAIN, GoalType.GENERAL_ENGINEERING}:
            try:
                kind = GoalType(previous_goal.get("goal_type"))
            except ValueError:
                pass
        timings = _timing(source)
        technology_constraints = _technologies(source)
        objects = _requested_objects(source)
        selected = context.get("selected_object_refs") or []
        targets = [{"id": str(item["id"]), "object_type": str(item.get("object_type") or item.get("type") or "Unknown")}
                   for item in selected if isinstance(item, dict) and item.get("id")]
        current_findings = context.get("unresolved_findings") or []
        finding_refs = [str(item.get("id") or item.get("finding_id")) for item in current_findings
                        if isinstance(item, dict) and (item.get("id") or item.get("finding_id"))]
        unresolved = []
        if kind == GoalType.REPAIR and not finding_refs:
            unresolved.append("Aktuelle Modellbefunde laden, bevor ein Reparaturumfang festgelegt wird.")
        return EngineeringGoal(goal_id=goal_id, goal_type=kind, original_request=source,
            project_context={"project_id": context.get("active_project_id"), "active_view": context.get("active_view"),
                             "model_revision": context.get("model_revision")},
            requested_objects=objects, requested_changes=[{"intent": kind.value}] if asked else [],
            timing_constraints=timings, technology_constraints=technology_constraints,
            target_objects=targets, user_constraints=list(context.get("user_constraints") or []),
            required_outcomes=list(_OUTCOMES.get(kind, ["evidence-backed-result"])),
            unresolved_decisions=unresolved, follow_up_of=str(follow_up_of) if follow_up_of else None)
