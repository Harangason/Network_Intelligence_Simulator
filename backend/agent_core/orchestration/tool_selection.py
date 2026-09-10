"""Keep local-model context bounded; further capabilities remain discoverable."""
from __future__ import annotations
import re


def select_tools(prompt: str, tools: list[dict]) -> list[dict]:
    names = {"inspect_project","search_model","inspect_object","ask_engineering_question","discover_engineering_tools"}
    spatial = bool(re.search(r'raum|spatial|zonal|einbauort|rotor|drohn|cluster|architecture|architektur|roboter|robot', prompt, re.I))
    if spatial:
        names.add('inspect_spatial_architecture')
    if re.search(r'\b(ändere|aendere|bearbeite|aktualisiere|update|modify)\b', prompt, re.I):
        names.add('update_object_via_proposal')
    groups = [
        (r"signal|semantik|semantics|encoding", {"inspect_signal","generate_signals","validate_signal","classify_signal_semantics","calculate_signal_bit_length","resolve_signal_emulator","generate_signal_behavior_proposal","find_similar_signals"}),
        (r"nachricht|message|pack", {"generate_messages","pack_function_messages","validate_message","calculate_message_size","calculate_bus_load","allocate_message_identifier"}),
        (r"route|routing|pfad", {"find_route_candidates","generate_routing","validate_route","rank_routes","inspect_route"}),
        (r"hardware|ecu|funktion|function|interface|schnittstelle|gerät|kamera|camera|wahrnehm", {"inspect_hardware","generate_functions","generate_hardware_interfaces","generate_function_interfaces","map_function_to_hardware","classify_device","get_device_capabilities","expand_requirement","generate_status_models","generate_data_objects"}),
        (r"netz|network|kapaz|capacity|bus|can|ethernet", {"inspect_network","calculate_capacity","calculate_bus_load","find_available_capacity","create_network_proposal","assign_network_to_interface","calculate_message_size"}),
        (r"simulation|simulier|szenario|scenario", {"validate_simulation_preflight","create_simulation_snapshot","start_simulation","get_simulation_status","get_simulation_results","generate_simulation_scenario"}),
        (r"trace|fehler|fault|anomal|golden", {"load_trace","analyze_trace","classify_trace_fault","find_trace_root_cause","correlate_signals","compare_golden_trace"}),
    ]
    for pattern, candidates in groups:
        if re.search(pattern,prompt,re.I):
            names.update(candidates)
    if len(names)==5:
        names.update({"inspect_findings","evaluate_architecture","find_graph_gaps"})
    reasoning_names = {"analyze_trace_root_cause", "explain_simulation_failure", "investigate_deadline_miss", "analyze_fault_effects",
                       "find_first_divergence", "compare_simulation_runs", "continue_reasoning", "inspect_reasoning", "get_trace_window"}
    if re.search(r"trace|ursach|reasoning|root.?cause|deadline|fault|golden|lauf.*vergleich", prompt, re.I):
        names.update(reasoning_names)
    selected = [tool for tool in tools if tool["name"] in names]
    return sorted(selected, key=lambda tool: (tool['name'] != 'inspect_spatial_architecture', tool["name"] not in reasoning_names))[:24]
