"""Capability-to-adapter registry. It describes existing MCP executors only."""
from __future__ import annotations

from dataclasses import dataclass
from .goal_resolver import GoalType


@dataclass(frozen=True)
class Capability:
    id: str
    tools: tuple[str, ...]
    purpose: str


CAPABILITIES: dict[GoalType, Capability] = {
    GoalType.CREATE_PROJECT: Capability("project.create", ("plan_simple_project", "prepare_project_request", "generate_wizard_model", "create_objects_via_proposal"), "Erstellen und prüfen eines Projektmodellentwurfs"),
    GoalType.CREATE_HARDWARE: Capability("hardware.create", ("prepare_hardware_request", "create_objects_via_proposal", "classify_device", "get_device_capabilities"), "Hardwareklassifikation und geprüfter Modellvorschlag"),
    GoalType.EXTEND_HARDWARE: Capability("hardware.channel", ("inspect_hardware_channel_request",
        "inspect_communication_capability", "inspect_controller_capacity", "find_free_channel",
        "prepare_hardware_channel", "validate_proposal"), "Bestätigte Controllerkapazität prüfen und einen einzelnen Hardwarekanal zur Freigabe vorbereiten"),
    GoalType.CREATE_FUNCTION: Capability("function.create", ("generate_functions", "map_function_to_hardware", "create_objects_via_proposal"), "Funktionen erstellen und ihrer bestätigten Hardware zuordnen"),
    GoalType.CREATE_SIGNAL: Capability("signal.create", ("generate_signals", "validate_signal", "create_objects_via_proposal"), "Signal anlegen und explizite Kodierung validieren"),
    GoalType.CREATE_NETWORK: Capability("network.create", ("create_network_proposal", "resolve_generation_rules", "validate_simulation_preflight"), "Technologiegebundenes Netz planen und validieren"),
    GoalType.CONNECT_OBJECTS: Capability("communication.connect", ("prepare_engineering_connection", "inspect_communication_feasibility", "generate_routing"), "Bestehende Kommunikationspfade nutzen oder Entscheidungsplan erstellen"),
    GoalType.PERIODIC_ACQUISITION: Capability("acquisition.periodic", ("inspect_model_situation", "generate_functions", "generate_messages", "generate_signals", "generate_routing", "calculate_capacity", "validate_simulation_preflight"), "Periodische Erfassung anhand vorhandener Daten und Kommunikation planen"),
    GoalType.CHANGE_CONFIGURATION: Capability("configuration.change", ("plan_lin_bitrate", "update_object_via_proposal", "calculate_capacity", "validate_simulation_preflight"), "Konfiguration vorschlagen und abhängige Berechnungen ausführen"),
    GoalType.VALIDATE_MODEL: Capability("model.validate", ("inspect_findings", "validate_simulation_preflight", "inspect_model_situation"), "Modell und Preflight prüfen"),
    GoalType.CALCULATE_CAPACITY: Capability("capacity.calculate", ("calculate_capacity", "inspect_network", "calculate_bus_load"), "Kapazität mit aktueller Netzwerktechnik berechnen"),
    GoalType.CALCULATE_TIMING: Capability("timing.calculate", ("calculate_capacity", "validate_simulation_preflight", "investigate_deadline_miss"), "Timing und Fristnachweise prüfen"),
    GoalType.RUN_SIMULATION: Capability("simulation.run", ("validate_simulation_preflight", "create_simulation_snapshot", "start_simulation", "get_simulation_status",
        "inspect_gateway_outage_request", "prepare_gateway_outage", "analyze_fault_effects", "assess_gateway_outage"), "Preflight-gebundene Simulation starten und nachweisen"),
    GoalType.ANALYZE_TRACE: Capability("trace.analyze", ("load_trace", "analyze_trace_root_cause", "find_trace_root_cause"), "Trace-Evidenz untersuchen"),
    GoalType.MEASURE_E2E: Capability("e2e.measure", ("analyze_trace_root_cause", "investigate_deadline_miss", "validate_simulation_preflight"), "E2E-Transaktionen korrelieren und messen"),
    GoalType.DIAGNOSE: Capability("diagnosis.inspect", ("inspect_message_timing", "inspect_message_trace_timing", "inspect_findings", "inspect_model_situation", "analyze_trace_root_cause", "investigate_deadline_miss"), "Ursachen auf Evidenzbasis untersuchen"),
    GoalType.REPAIR: Capability("repair.apply", ("inspect_findings", "inspect_communication_repair", "prepare_communication_repair", "update_object_via_proposal",
        "inspect_signal_recipients", "prepare_signal_recipient_repair"), "Fehlerumfang ermitteln und validierten Reparaturvorschlag vorbereiten"),
    GoalType.OPTIMIZE: Capability("network.optimize", ("calculate_capacity", "find_available_capacity", "evaluate_architecture"), "Optimierung mit aktuellen Last- und Gültigkeitsdaten bewerten"),
    GoalType.EXPLAIN: Capability("engineering.explain", ("inspect_communication_path", "inspect_model_situation", "search_model", "inspect_findings"), "Projektbezogene Frage anhand des kanonischen Modells beantworten"),
    GoalType.COMPARE: Capability("engineering.compare", ("compare_simulation_runs", "evaluate_architecture", "compare_golden_trace"), "Architekturen oder Läufe anhand gemeinsamer Kriterien vergleichen"),
    GoalType.REMOVE: Capability("model.remove", ("delete_object_via_impact_analysis", "inspect_model_situation"), "Entfernungsfolgen analysieren und gezielt vorschlagen"),
    GoalType.STATUS_QUERY: Capability("system.status", ("inspect_project", "inspect_findings", "validate_simulation_preflight", "get_simulation_status", "calculate_capacity"), "Aktuellen Modell-, Befund- und Messstatus berichten"),
    GoalType.GENERAL_ENGINEERING: Capability("engineering.general", ("inspect_project", "search_model", "discover_engineering_tools", "ask_engineering_question"), "Engineering-Anforderung klassifizieren und passende Fähigkeiten bestimmen"),
}


class CapabilityRegistry:
    def resolve(self, goal_type: GoalType, available_tools: list[dict] | set[str] | tuple[str, ...]) -> dict:
        capability = CAPABILITIES[goal_type]
        names = {item if isinstance(item, str) else item.get("name") for item in available_tools}
        available = [name for name in capability.tools if name in names]
        executable = bool(available)
        mutation_adapters = {
            GoalType.CREATE_PROJECT: {'plan_simple_project', 'generate_wizard_model', 'create_objects_via_proposal'},
            GoalType.CREATE_HARDWARE: {'prepare_hardware_request', 'create_objects_via_proposal'},
            GoalType.EXTEND_HARDWARE: {'prepare_hardware_channel'},
            GoalType.CREATE_FUNCTION: {'generate_functions', 'create_objects_via_proposal'},
            GoalType.CREATE_SIGNAL: {'generate_signals', 'create_objects_via_proposal'},
            GoalType.CREATE_NETWORK: {'create_network_proposal', 'generate_wizard_network', 'create_objects_via_proposal'},
            GoalType.CONNECT_OBJECTS: {'prepare_engineering_connection', 'generate_routing'},
            GoalType.CHANGE_CONFIGURATION: {'plan_lin_bitrate', 'update_object_via_proposal'},
            GoalType.REPAIR: {'prepare_communication_repair', 'update_object_via_proposal', 'prepare_signal_recipient_repair'},
            GoalType.REMOVE: {'delete_object_via_impact_analysis'},
        }
        if goal_type in mutation_adapters:
            executable = bool(mutation_adapters[goal_type] & names)
        elif goal_type == GoalType.PERIODIC_ACQUISITION:
            executable = {'generate_functions', 'validate_proposal'} <= names
        elif goal_type == GoalType.RUN_SIMULATION:
            executable = {'validate_simulation_preflight', 'create_simulation_snapshot',
                          'start_simulation', 'get_simulation_status'} <= names
        return {"capability_id": capability.id, "purpose": capability.purpose,
                "required_tools": list(capability.tools), "available_tools": available,
                "available": executable, "missing_tools": [name for name in capability.tools if name not in names]}
