"""Keep local-model context bounded; further capabilities remain discoverable."""
from __future__ import annotations
import re


def select_tools(prompt: str, tools: list[dict]) -> list[dict]:
    # A terminology question does not identify a canonical object. Give the
    # model the definition tool rather than inviting invented object UUIDs.
    concepts = (re.search(r'\b(?:wozu|unterschied zwischen|was ist (?:ein|eine)|was sind|was bedeutet|what is (?:a|an)|difference between)\b', prompt, re.I)
                and re.search(r'hardware|funktion|function|signal|nachricht|message|interface|anschluss', prompt, re.I)
                and not re.search(r'projekt|aktuellen?|konkreten?|ausgewählt|selected|[0-9a-f]{8}-', prompt, re.I))
    if concepts:
        return [tool for tool in tools if tool['name'] in {'describe_engineering_concepts', 'inspect_assistant_capabilities', 'prepare_assistant_action'}]
    names = {"inspect_project","search_model","inspect_object","ask_engineering_question","discover_engineering_tools", "type_engineering_input",
             "inspect_assistant_capabilities", "prepare_assistant_action"}
    focused = set()
    from .project_intake import is_project_request
    if is_project_request(prompt):
        names.add('prepare_project_request')
    if re.search(r'projekt|project|entwurf|draft', prompt, re.I):
        focused.update({'inspect_project_draft', 'update_project_draft', 'plan_project_model', 'create_project_from_draft'})
    if re.search(r'anleg|erstell|erzeug|hinzufüg|create|generate|add', prompt, re.I):
        focused.update({'describe_model_object_fields', 'create_objects_via_proposal'})
    if re.search(r'zuordn|verschieb|hierarch|assign|move', prompt, re.I):
        focused.update({'evaluate_structure_dependencies', 'plan_structure_assignments', 'map_function_to_hardware'})
    if re.search(r'lösch|loesch|entfern|delete|remove', prompt, re.I):
        focused.add('delete_object_via_impact_analysis')
    if re.search(r'verbind|connect|anschluss|controller|port|gesamtplan', prompt, re.I):
        names.update({'prepare_engineering_connection', 'continue_engineering_goal', 'inspect_engineering_goal',
            'inspect_model_situation', 'inspect_port_decision', 'inspect_controller_capacity'})
    if re.search(r'repar|neue.*(?:weg|route|architektur)|funktionspartner', prompt, re.I):
        names.update({'inspect_communication_repair', 'prepare_communication_repair', 'continue_communication_repair'})
    if re.search(r'dublett|duplicat|struktur.*transfer|structure.*transfer', prompt, re.I):
        names.update({'inspect_system_duplicates', 'analyze_structure_transfer', 'inspect_model_situation'})
        focused.add('plan_structure_transfer')
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
    if len(names)==8:
        names.update({"inspect_findings","evaluate_architecture","find_graph_gaps"})
    reasoning_names = {"analyze_trace_root_cause", "explain_simulation_failure", "investigate_deadline_miss", "analyze_fault_effects",
                       "find_first_divergence", "compare_simulation_runs", "continue_reasoning", "inspect_reasoning", "get_trace_window"}
    if re.search(r"trace|ursach|reasoning|root.?cause|deadline|fault|golden|lauf.*vergleich", prompt, re.I):
        names.update(reasoning_names)
    names.update(focused)
    if re.search(r'import|datei.*(?:übernehm|einles)|file.*(?:load|read)', prompt, re.I):
        focused.update({'preview_model_import', 'plan_model_import', 'plan_project_bundle_restore'})
        names.update(focused)
    if re.search(r'export|projekt.*(?:herunterladen|download)', prompt, re.I):
        focused.add('export_project_bundle')
        names.update(focused)
    if re.search(r'fehlerszenario|fehler.*aktiv|fault.*(?:scenario|activ)|fehler.*vorschl', prompt, re.I):
        focused.update({'generate_fault_proposals', 'plan_fault_activation'})
        names.update(focused)
    selected = [tool for tool in tools if tool["name"] in names]
    return sorted(selected, key=lambda tool: (tool['name'] not in {'prepare_engineering_connection', 'continue_engineering_goal', 'inspect_engineering_goal', 'inspect_assistant_capabilities', 'prepare_assistant_action', 'inspect_communication_repair', 'inspect_spatial_architecture'} | focused, tool["name"] not in reasoning_names))[:24]
