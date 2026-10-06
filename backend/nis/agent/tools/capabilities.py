"""Executable assistant directory shared by chat, MCP and the UI.

Entries describe existing workflows. Opening one never grants model write authority.
"""
from __future__ import annotations

from copy import deepcopy
from backend.nis.engineering.projects.project_context import current_project_id
from backend.nis.workflow.services.service import WorkflowStatusService


def entry(id, label, description, path, tools, steps, *, resource=None, launch=None):
    return dict(id=id, label=label, description=description, path=path,
                tools=tools, steps=steps, resource=resource, launch=launch)


def prepare_project_request(arguments):
    from backend.nis.agent.orchestration.project_intake import project_intake_text
    from backend.nis.agent.tools import project_draft as project_draft
    from uuid import uuid4
    requirement = arguments['requirement'].strip()
    if not requirement:
        raise ValueError('Eine Projektanforderung ist erforderlich.')
    current = project_draft.inspect()
    revision = arguments['revision'] if 'revision' in arguments else (current or {}).get('revision')
    saved = project_draft.command({
        'action': 'AMEND' if revision is not None else 'CREATE',
        'operation_id': arguments.get('operation_id') or str(uuid4()),
        'revision': revision,
        'requirement': requirement,
    })
    draft = saved['draft']
    directory = catalog({'capability_id': 'project'})
    item = directory['capabilities'][0]
    if not item['available']:
        raise ValueError('Der Engineering-Wizard ist momentan nicht verfügbar.')
    action = {**item['action'], 'label': 'Im Wizard bearbeiten',
              'description': 'Gespeicherten Entwurf ergänzen und prüfen',
              'draft_id': draft['draft_id'],
              'requirement': '\n'.join(source['text'] for source in draft['sources'])}
    notes = arguments.get('planning_notes', '').strip()
    text = project_intake_text(requirement, draft['devices'])
    if notes:
        text += '\n\nKI-Planungsvorschlag zur Prüfung:\n' + notes
    text += '\n\nGespeicherter Entwurf, Revision ' + str(draft['revision']) + '. Offene Angaben:\n'
    text += '\n'.join('- ' + issue['message'] for issue in draft['issues'][:20]) or 'Keine offenen Inventarangaben.'
    return {'agent_response': {'type': 'RESULT', 'status': 'INCOMPLETE',
                              'text': text, 'actions': [action],
                              'metadata': {'planning_mode': 'model_assisted' if notes else 'guided_intake',
                                           'project_draft_id': draft['draft_id'], 'draft_revision': draft['revision']}}}


CAPABILITIES = [
    entry('signal', 'Signal anlegen', 'Signal mit Bedeutung, Einheit, Wertebereich und expliziter Kodierung anlegen.', '/studio/engineering',
          ['generate_signals', 'validate_signal'], ['Identität', 'Nachricht zuordnen', 'Kodierung und Zeitverhalten', 'Prüfen und speichern'], resource='signals', launch='create'),
    entry('message', 'Nachricht anlegen', 'Publisher, Anschluss, Signale und Sendeverhalten festlegen.', '/studio/engineering',
          ['generate_messages', 'validate_message'], ['Identität', 'Interface und physischer Anschluss', 'Payload und Sendeverhalten', 'Prüfen und speichern'], resource='messages', launch='create'),
    entry('function', 'Funktion anlegen', 'Funktion und ihre Hardware-Zuordnung modellieren.', '/studio/engineering',
          ['generate_functions', 'map_function_to_hardware'], ['Identität', 'Hardware zuordnen', 'Funktionsparameter', 'Prüfen und speichern'], resource='functions', launch='create'),
    entry('hardware', 'Hardware anlegen', 'ECU, Gateway, Sensor oder Aktor mit Geräteklasse erfassen.', '/studio/engineering',
          ['classify_device', 'get_device_capabilities', 'create_objects_via_proposal'], ['Identität und Gerätetyp', 'Zuordnung', 'Technische Details', 'Prüfen und speichern'], resource='hardware-nodes', launch='create'),
    entry('port', 'Physischen Anschluss anlegen', 'Hardwarefähigkeit, Controller und Kanalgrenzen prüfen. Im Chat plant „Verbinde Funktion A mit Funktion B“ den vollständigen Anschlussauftrag; nach der Strategieentscheidung werden Port, Netz, Routing und Prüfungen ausgeführt.', '/studio/engineering',
          ['inspect_port_decision', 'prepare_engineering_connection', 'create_physical_port', 'connect_port_to_network', 'continue_engineering_goal'], ['Modell und Hardwaregrenzen', 'Anschlussentscheidung', 'Abhängige Änderungen ausführen', 'Kapazität, Timing und Preflight'], resource='hardware-interfaces', launch='create'),
    entry('interface', 'Kommunikationsschnittstelle anlegen', 'Logische Schnittstelle einer Funktion oder eines Geräts anlegen.', '/studio/engineering',
          ['generate_function_interfaces'], ['Identität', 'Funktion oder Gerät', 'Kommunikationsparameter', 'Prüfen und speichern'], resource='interfaces', launch='create'),
    entry('repair', 'Reparatur-Agent', 'Kennt die aktuelle Hardwarearchitektur und erhält die bisherigen Funktionspartner. Vergleicht alte und neue Signalwege einschließlich der Routing-Tabelle. Neue Führung übernehmen oder alte Führung wiederherstellen wird ausdrücklich entschieden; fehlende Wege und ein Wechsel zwischen Systemnetz und Cluster bleiben sichtbar.', '/studio/engineering',
          ['inspect_communication_repair', 'prepare_communication_repair', 'continue_communication_repair'], ['Aktuelle Architektur und Funktionspartner lesen', 'Fachagent bewertet alte und neue Wege', 'Strategie wählen', 'Atomar übernehmen und erneut prüfen'], launch='repair'),
    entry('project', 'Projekt planen und ausführen', 'Aus Anforderungen und Dokumenten einen geprüften Projektentwurf erstellen. Entscheidungen, Modellvorschlag und Ergebnisse können im Chat bearbeitet werden.', '/studio/engineering',
          ['prepare_project_request', 'inspect_project_draft', 'update_project_draft', 'create_project_from_draft', 'plan_project_model', 'prepare_draft_workflow', 'generate_wizard_model', 'generate_wizard_communication_contract', 'generate_wizard_routing', 'generate_wizard_network', 'generate_wizard_parameters', 'preview_model_import', 'plan_model_import', 'export_project_bundle', 'plan_project_bundle_restore'], ['Anforderung und Domäne', 'Geräte, Funktionen und räumliche Zuordnung', 'Kommunikation und Routing', 'Parameter, Kapazität und Preflight', 'Simulation und Auswertung'], launch='project'),
    entry('routing', 'Routing planen', 'Producer und Consumer über die aktuelle physische Architektur verbinden.', '/studio/routing',
          ['find_route_candidates', 'generate_routing', 'validate_route'], ['Kommunikationspartner', 'Physische Wege', 'Validierung', 'Vorschlag prüfen']),
    entry('structure', 'KI-Strukturtransfer', 'Bestehende ECU-Strukturen analysieren und je Ziel-ECU geprüft übertragen.', '/studio/engineering',
          ['analyze_structure_transfer', 'plan_structure_transfer'], ['Quell-ECU', 'Ziel-ECUs', 'Übereinstimmungen und Unterschiede', 'Je Ziel prüfen und übernehmen'], launch='structure'),
    entry('spatial', 'Raumarchitektur prüfen', 'Bestätigte Einbauorte, Raumcluster und offene Zuordnungen prüfen.', '/studio',
          ['inspect_spatial_architecture'], ['Bezugsrahmen', 'Zuordnungen und Quellen', 'Konflikte', 'Gezielte Klärung']),
    entry('parameters', 'Parameter auslegen', 'Technologie-, Kommunikations- und Zeitparameter aus dem Modell ableiten.', '/studio',
          ['generate_wizard_parameters'], ['Modellvorgaben', 'Technologie und Sendeverhalten', 'Randbedingungen', 'Validierung']),
    entry('capacity', 'Kapazität und Timing prüfen', 'Nutzlast, Buslast, Sendeplan und Funktionsfristen getrennt bewerten.', '/studio/capacity',
          ['calculate_capacity', 'plan_capacity_remediation'], ['Aktuelle Routen', 'Kapazität und Sendeplan', 'Befunde', 'Abhilfe prüfen']),
    entry('validation', 'Preflight prüfen', 'Modell, Kommunikation und Simulationsfähigkeit prüfen.', '/studio/validation',
          ['validate_simulation_preflight'], ['Modellstand', 'Kommunikationsvertrag', 'Fehler und offene Punkte', 'Freigabeentscheidung']),
    entry('simulation', 'Simulation vorbereiten', 'Szenario, Fehler und Umfang wählen; einen echten Simulationslauf starten.', '/studio/simulation',
          ['generate_simulation_scenario', 'create_simulation_snapshot', 'start_simulation', 'get_simulation_status', 'get_simulation_results'], ['Szenario', 'Signale und Fehler', 'Preflight', 'Start und Ergebnisse']),
    entry('analysis', 'Ursachenanalyse', 'Trace-Evidenz, Fristverletzungen und Fehlerwirkungen mit den Analyseagenten untersuchen.', '/studio/trace-analysis',
          ['analyze_trace_root_cause', 'investigate_deadline_miss', 'analyze_fault_effects', 'compare_simulation_runs'], ['Lauf wählen', 'Zeitfenster und Auffälligkeit', 'Evidenz prüfen', 'Ursache und Grenzen erklären']),
    entry('intelligence', 'Intelligence bewerten', 'Architektur und Erfahrungen aus vorhandenen Läufen bewerten.', '/studio/intelligence',
          ['evaluate_architecture', 'assess_intelligence'], ['Projekt und Läufe', 'Bewertung', 'Verbesserungsvorschläge', 'Prüfung']),
    entry('dependencies', 'Structure Wizard', 'Abhängigkeiten zwischen Hardware, Funktionen, Interfaces, Nachrichten und Signalen mit semantischer Bewertung zuordnen.', '/studio/engineering',
          ['evaluate_structure_dependencies', 'plan_structure_assignments'], ['Hardware wählen', 'Funktionen, Interfaces, Nachrichten und Signale', 'Semantische Zuordnung prüfen', 'Abhängigkeiten übernehmen'], launch='dependencies'),
    entry('duplicates', 'System-Dubletten prüfen', 'Mögliche doppelte Systeme anhand ihrer Strukturen vergleichen; Zusammenführen wird geprüft.', '/studio/engineering',
          ['inspect_system_duplicates'], ['Systemstrukturen vergleichen', 'Ähnlichkeiten und Unterschiede', 'Kandidat prüfen', 'Zusammenführen entscheiden'], launch='tree'),
    entry('faults', 'KI-Fehlervorschläge', 'Zum aktuellen Modell passende Fehlerszenarien vorbereiten und vor Aktivierung prüfen.', '/studio/simulation',
          ['generate_fault_proposals', 'plan_fault_activation'], ['Aktuelles Modell', 'Fehlervorschläge', 'Magnitude und Umfang', 'Prüfen und aktivieren']),
]

# Stable wizard IDs used by the Engineering Assistant entry points and by the
# NIS capability contract. Each entry resolves only to tools already registered
# above; the aliases do not add permissions or bypass the normal review gates.
WIZARD_CAPABILITIES = [
    entry('architecture.create', 'Architektur erstellen', 'Architektur aus dem Auftrag planen und als prüfbaren Vorschlag ausführen.', '/studio/engineering',
          ['prepare_project_request', 'inspect_project_draft', 'plan_project_model', 'prepare_draft_workflow', 'generate_wizard_model', 'generate_wizard_communication_contract', 'generate_wizard_routing', 'generate_wizard_network', 'generate_wizard_parameters'],
          ['Anforderung erfassen', 'Modell und Kommunikation planen', 'Vorschlag prüfen', 'Freigabe und Validierung'], launch='project'),
    entry('signal.validate', 'Signal prüfen', 'Ein Signal anhand seiner Bedeutung, Einheit, Werte und Nachrichtenbindung prüfen.', '/studio/engineering',
          ['inspect_signal', 'resolve_signal_encoding', 'validate_signal'],
          ['Signal und Nachricht lesen', 'Kodierung prüfen', 'Befunde und Validierung'], resource='signals', launch='validate'),
    entry('trace.analyze', 'Trace analysieren', 'Einen vorhandenen Simulations-Trace mit aktueller Modell- und Laufrevision untersuchen.', '/studio/trace-analysis',
          ['inspect_message_trace_timing', 'analyze_trace_root_cause', 'get_trace_events', 'get_signal_series', 'get_fault_events', 'get_route', 'get_timing_metrics', 'continue_reasoning'],
          ['Lauf und Zeitfenster wählen', 'Trace-Evidence prüfen', 'Ursache und Grenzen bewerten']),
    entry('finding.review', 'Finding bewerten', 'Ein persistiertes Finding und seine aktuelle Evidence bewerten; keine Änderung ohne separate Freigabe.', '/studio/trace-analysis',
          ['inspect_reasoning', 'analyze_trace_root_cause', 'investigate_deadline_miss', 'analyze_fault_effects'],
          ['Finding und Modellrevision lesen', 'Ursache anhand der Evidence bewerten', 'Befund und offene Punkte dokumentieren']),
]

CONCEPTS = {
    'HardwareNode': 'Physisches Gerät, beispielsweise ECU, Gateway, Sensor oder Aktor.',
    'Function': 'Logische Aufgabe mit einer Zuordnung zur ausführenden Hardware.',
    'HardwareNetworkInterface': 'Physischer Anschluss mit Technologie, Kanal und Netzzuordnung.',
    'Interface': 'Logische Kommunikationsschnittstelle einer Funktion oder eines Geräts.',
    'Message': 'Transportiert ein Bündel von Signalen von einem Publisher über einen physischen Anschluss.',
    'Signal': 'Einzeln kodierter Messwert, Sollwert, Status oder Rückmeldung mit Wertebereich und Bedeutung. Kein Kommunikationskanal.',
}


# Explicit outcomes, not inferred from a button label or tool permission. Some
# VALIDATE tools persist assessments, while some GENERATE tools only analyze.
EXECUTION_CONTRACTS = {
    **{key: ('REVIEWABLE_PROPOSAL', ['PROPOSAL', 'FINDING', 'VALIDATION'],
             'Aktuelle menschliche Freigabe und erfolgreicher Apply mit kanonischen IDs.')
       for key in ('signal', 'message', 'function', 'hardware', 'interface', 'routing', 'dependencies', 'structure', 'faults')},
    'project': ('REVIEWABLE_PROPOSAL', ['PROPOSAL', 'FINDING', 'VALIDATION'],
                'Modellübernahme und aktuelle Artefakte für jeden ausdrücklich beauftragten Workflowschritt.'),
    'architecture.create': ('REVIEWABLE_PROPOSAL', ['PROPOSAL', 'FINDING', 'VALIDATION'],
                            'Aktueller Architekturvorschlag, ausdrückliche Freigabe und kanonische Modellvalidierung.'),
    'signal.validate': ('ANALYSIS_ONLY', ['FINDING', 'VALIDATION'],
                        'Aktuelle Signal- und Nachrichtenvalidierung mit nachvollziehbaren Pflichtfeldern.'),
    'trace.analyze': ('ANALYSIS_ONLY', ['FINDING', 'VALIDATION'],
                      'Trace-Analyse mit aktueller Laufrevision und Evidence; keine Modelländerung.'),
    'finding.review': ('ANALYSIS_ONLY', ['FINDING', 'VALIDATION'],
                       'Bewertung mit aktueller Evidence und Revision; keine Modelländerung.'),
    'port': ('AUTHORIZED_EXECUTION', ['MODEL_CHANGE', 'FINDING', 'VALIDATION'],
             'Gespeicherte Strategieentscheidung, ausgeführte Teilaufträge und aktuelle Abschlussprüfungen.'),
    'repair': ('AUTHORIZED_EXECUTION', ['MODEL_CHANGE', 'FINDING', 'VALIDATION'],
               'Gespeicherte Reparaturentscheidung, atomare Übernahme und erneute technische Prüfung.'),
    'parameters': ('PERSISTED_ASSESSMENT', ['MODEL_CHANGE', 'VALIDATION'],
                   'Bestätigte Parameter gespeichert und gegen den aktuellen Modellstand geprüft.'),
    'intelligence': ('PERSISTED_ASSESSMENT', ['FINDING', 'VALIDATION'],
                     'Bewertung mit aktuellem Modell- und Laufbezug gespeichert.'),
    'simulation': ('SIMULATION_JOB', ['PROPOSAL', 'FINDING', 'VALIDATION'],
                   'Echter Job erfolgreich abgeschlossen; passende Ergebnisse und Trace vorhanden.'),
    **{key: ('ANALYSIS_ONLY', ['FINDING', 'VALIDATION'],
             'Analyse geliefert; dies bestätigt keine Übernahme vorgeschlagener Änderungen.')
       for key in ('spatial', 'capacity', 'validation', 'analysis', 'duplicates')},
}


def catalog(arguments):
    from backend.nis.agent.api.tool_contract import Permission
    from backend.nis.agent.tools.catalog import TOOLS
    from backend.nis.agent.tools.runtime import DEFAULT_PERMISSIONS
    from backend.nis.agent.registry.skill_registry import SkillRegistry
    from backend.nis.agent.api.input_output import INPUT_TYPES
    from backend.nis.agent.api.input_output import SUPPORTED_INPUTS
    permissions = arguments.get('_permissions', DEFAULT_PERMISSIONS)
    requested = arguments.get('capability_id')
    items = [deepcopy(item) for item in [*CAPABILITIES, *WIZARD_CAPABILITIES]
             if not requested or item['id'] == requested]
    if not items:
        raise ValueError('Diese Fähigkeit ist nicht registriert.')
    state = WorkflowStatusService(current_project_id()).get(summary=True)
    settings = (state.get('context') or {}).get('engineering_wizard_settings') or {}
    for item in items:
        item['available'] = all(name in TOOLS and TOOLS[name].permission in permissions for name in item['tools'])
        mode, outputs, completion = EXECUTION_CONTRACTS[item['id']]
        item['execution'] = {'mode': mode, 'outputs': outputs, 'completion_condition': completion,
                             'navigation_executes': False,
                             'agent_can_apply': item['available'] and (
                                 (mode == 'REVIEWABLE_PROPOSAL' and Permission.APPLY_APPROVED_PROPOSAL in permissions)
                                 or (mode == 'AUTHORIZED_EXECUTION' and Permission.EXECUTE_AUTHORIZED_GOAL in permissions)
                                 or mode == 'PERSISTED_ASSESSMENT'),
                             'requires_human_model_approval': mode in {'REVIEWABLE_PROPOSAL', 'AUTHORIZED_EXECUTION'},
                             'ui_only_completion': mode == 'UI_REVIEW_REQUIRED'}
        item['action'] = {'type': 'CAPABILITY', 'capability_id': item['id'], 'label': item['label'],
                          'description': item['description'], 'project_id': current_project_id(),
                          'execution_mode': mode, 'navigation_executes': False}
    return {'project_id': current_project_id(), 'project_name': settings.get('project_name') or current_project_id(),
            'capabilities': items, 'skill_contracts': SkillRegistry(items, TOOLS).contracts(permissions),
            'input_adapters': [{'input_type': kind, 'available': kind in SUPPORTED_INPUTS} for kind in INPUT_TYPES]}


def prepare_action(arguments):
    result = catalog(arguments)
    item = result['capabilities'][0]
    if not item['available']:
        raise ValueError('Die benötigten Fachwerkzeuge sind nicht verfügbar.')
    return {'agent_response': {'type': 'RESULT', 'status': 'ANSWERED',
            'text': item['description'], 'actions': [item['action']]}}


def repair_preview(_):
    from backend.nis.engineering.communication.communication_repair import load_plan
    from backend.nis.engineering.communication.communication_repair import public_plan
    from backend.nis.engineering.communication.communication_repair import complete_plan
    planner, _ = load_plan()
    result = public_plan(complete_plan(planner))
    result['project_id'] = current_project_id()
    return result


def structure_preview(arguments):
    from backend.nis.engineering.structure.structure_transfer import analyze_ecu_transfer
    from backend.nis.agent.tools.specialist import review_or_report
    result = analyze_ecu_transfer({'source_hardware_id': arguments.get('source_hardware_id'),
                                 'target_hardware_ids': arguments.get('target_hardware_ids')})
    result['agent_review'] = review_or_report('ECU-Strukturtransfer: Quellstruktur und jedes Ziel auf fachliche Eignung prüfen',
        [{'id': target['proposal_id'], **target} for target in result['targets']])
    return result


def structure_evaluate(arguments):
    from backend.nis.engineering.structure.structure import evaluate_structure
    from backend.nis.agent.tools.specialist import review_or_report
    result = evaluate_structure({'selections': arguments['selection']})
    result['agent_review'] = review_or_report('Abhängigkeiten: kanonische Hierarchie und Bedeutung jeder vorgeschlagenen Zuordnung prüfen',
        [{'id': item['child_type'] + ':' + item['child_id'], **item} for item in result['suggestions']])
    return {'analysis': result}


def structure_assignments(arguments):
    from backend.nis.engineering.structure.structure import assignment_updates
    from backend.nis.agent.tools import proposal_service as proposal_service
    changes = []
    seen = set()
    allowed = {'child_type', 'child_id', 'parent_type', 'parent_id', 'name'}
    for assignment in arguments['assignments']:
        if set(assignment) - allowed:
            raise ValueError('Strukturzuordnungen enthalten nicht unterstützte Felder.')
        kind, identifier, updates = assignment_updates(assignment)
        if (kind, identifier) in seen:
            raise ValueError('Ein Objekt darf je Vorschlag nur einem Elternobjekt zugeordnet werden.')
        seen.add((kind, identifier))
        changes.append({'object_type': kind, 'object_id': identifier, 'action': 'UPDATE', 'data': updates})
    proposal = proposal_service.create('STRUCTURE_ASSIGNMENTS', changes, arguments['rationale'],
                                      evidence=[{'source': 'structure.assignment_updates'}])
    return proposal_service.validate(proposal['proposal_id'])


def duplicates_preview(_):
    from backend.nis.engineering.structure.structure_transfer import analyze_system_duplicates
    return analyze_system_duplicates()


def fault_proposals(_):
    from backend.nis.engineering.simulation import propose_faults
    return {'items': propose_faults(model_review=True), 'review': 'simulation-fault-proposals'}


def plan_fault_activation(arguments):
    from backend.nis.engineering.simulation import list_fault_proposals
    from backend.nis.agent.tools import generation as generation
    from backend.nis.agent.tools import proposal_service as proposal_service
    available = {str(item['proposal_id']): item for item in list_fault_proposals()}
    selected = arguments['fault_proposal_ids']
    if len(set(selected)) != len(selected) or any(key not in available for key in selected):
        raise ValueError('Eindeutige Fehlervorschläge aus dem aktuellen Projekt wählen.')
    faults = []
    for key in selected:
        item = available[key]
        if item['status'] == 'REJECTED':
            raise ValueError('Ein abgelehnter Fehlervorschlag kann nicht aktiviert werden.')
        faults.append({**item['configuration'], 'target': item['target'], 'scope': item['fault_scope'],
                       'type': item['fault_type'], 'proposal_id': key})
    proposal = generation.scenario({'scenario': {'name': arguments['name'], 'mode': 'AI_GENERATED_FAULT',
        'duration_s': arguments['duration_s'], 'faults': faults}, 'prompt': arguments['rationale']})
    return proposal_service.validate(proposal['proposal_id'])
