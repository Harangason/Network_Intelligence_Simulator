"""Executable assistant directory shared by chat, MCP and the UI.

Entries describe existing workflows. Opening one never grants model write authority.
"""
from __future__ import annotations

from copy import deepcopy
from ..project_context import current_project_id
from ..workflow.service import WorkflowStatusService


def entry(id, label, description, path, tools, steps, *, resource=None, launch=None):
    return dict(id=id, label=label, description=description, path=path,
                tools=tools, steps=steps, resource=resource, launch=launch)


CAPABILITIES = [
    entry('signal', 'Signal anlegen', 'Signal mit Bedeutung, Einheit, Wertebereich und expliziter Kodierung anlegen.', '/studio/engineering',
          ['generate_signals', 'validate_signal'], ['Identität', 'Nachricht zuordnen', 'Kodierung und Zeitverhalten', 'Prüfen und speichern'], resource='signals', launch='create'),
    entry('message', 'Nachricht anlegen', 'Publisher, Anschluss, Signale und Sendeverhalten festlegen.', '/studio/engineering',
          ['generate_messages', 'validate_message'], ['Identität', 'Interface und physischer Anschluss', 'Payload und Sendeverhalten', 'Prüfen und speichern'], resource='messages', launch='create'),
    entry('function', 'Funktion anlegen', 'Funktion und ihre Hardware-Zuordnung modellieren.', '/studio/engineering',
          ['generate_functions', 'map_function_to_hardware'], ['Identität', 'Hardware zuordnen', 'Funktionsparameter', 'Prüfen und speichern'], resource='functions', launch='create'),
    entry('hardware', 'Hardware anlegen', 'ECU, Gateway, Sensor oder Aktor mit Geräteklasse erfassen.', '/studio/engineering',
          ['classify_device', 'get_device_capabilities'], ['Identität und Gerätetyp', 'Zuordnung', 'Technische Details', 'Prüfen und speichern'], resource='hardware-nodes', launch='create'),
    entry('port', 'Physischen Anschluss anlegen', 'Hardware, Technologie, Kanal und physisches Netz verbinden.', '/studio/engineering',
          ['generate_hardware_interfaces', 'assign_network_to_interface'], ['Identität', 'Hardware und Netz', 'Kanal und Technologie', 'Prüfen und speichern'], resource='hardware-interfaces', launch='create'),
    entry('interface', 'Kommunikationsschnittstelle anlegen', 'Logische Schnittstelle einer Funktion oder eines Geräts anlegen.', '/studio/engineering',
          ['generate_function_interfaces'], ['Identität', 'Funktion oder Gerät', 'Kommunikationsparameter', 'Prüfen und speichern'], resource='interfaces', launch='create'),
    entry('repair', 'Reparatur-Agent', 'Kennt die aktuelle Hardwarearchitektur und erhält die bisherigen Funktionspartner. Vergleicht alte und neue Signalwege einschließlich der Routing-Tabelle. Neue Führung übernehmen oder alte Führung wiederherstellen wird ausdrücklich entschieden; fehlende Wege und ein Wechsel zwischen Systemnetz und Cluster bleiben sichtbar.', '/studio/engineering',
          ['inspect_communication_repair'], ['Aktuelle Architektur und Funktionspartner lesen', 'Alte und neue Wege vergleichen', 'Strategie wählen', 'Atomar übernehmen und erneut prüfen'], launch='repair'),
    entry('project', 'Engineering-Wizard', 'Aus Anforderungen und Dokumenten das Projekt stufenweise bis zur Auswertung entwickeln.', '/studio/engineering',
          ['generate_wizard_model', 'generate_wizard_communication_contract', 'generate_wizard_routing', 'generate_wizard_network', 'generate_wizard_parameters'], ['Anforderung und Domäne', 'Geräte, Funktionen und räumliche Zuordnung', 'Kommunikation und Routing', 'Parameter, Kapazität und Preflight', 'Simulation und Auswertung'], launch='project'),
    entry('routing', 'Routing planen', 'Producer und Consumer über die aktuelle physische Architektur verbinden.', '/studio/routing',
          ['find_route_candidates', 'generate_routing', 'validate_route'], ['Kommunikationspartner', 'Physische Wege', 'Validierung', 'Vorschlag prüfen']),
    entry('structure', 'KI-Strukturtransfer', 'Bestehende ECU-Strukturen analysieren und je Ziel-ECU geprüft übertragen.', '/studio/engineering',
          ['analyze_structure_transfer'], ['Quell-ECU', 'Ziel-ECUs', 'Übereinstimmungen und Unterschiede', 'Je Ziel prüfen und übernehmen'], launch='structure'),
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
          ['evaluate_structure_dependencies'], ['Hardware wählen', 'Funktionen, Interfaces, Nachrichten und Signale', 'Semantische Zuordnung prüfen', 'Abhängigkeiten übernehmen'], launch='dependencies'),
    entry('duplicates', 'System-Dubletten prüfen', 'Mögliche doppelte Systeme anhand ihrer Strukturen vergleichen; Zusammenführen wird geprüft.', '/studio/engineering',
          ['inspect_system_duplicates'], ['Systemstrukturen vergleichen', 'Ähnlichkeiten und Unterschiede', 'Kandidat prüfen', 'Zusammenführen entscheiden'], launch='tree'),
    entry('faults', 'KI-Fehlervorschläge', 'Zum aktuellen Modell passende Fehlerszenarien vorbereiten und vor Aktivierung prüfen.', '/studio/simulation',
          ['generate_fault_proposals'], ['Aktuelles Modell', 'Fehlervorschläge', 'Magnitude und Umfang', 'Prüfen und aktivieren']),
]

CONCEPTS = {
    'HardwareNode': 'Physisches Gerät, beispielsweise ECU, Gateway, Sensor oder Aktor.',
    'Function': 'Logische Aufgabe mit einer Zuordnung zur ausführenden Hardware.',
    'HardwareNetworkInterface': 'Physischer Anschluss mit Technologie, Kanal und Netzzuordnung.',
    'Interface': 'Logische Kommunikationsschnittstelle einer Funktion oder eines Geräts.',
    'Message': 'Transportiert ein Bündel von Signalen von einem Publisher über einen physischen Anschluss.',
    'Signal': 'Einzeln kodierter Messwert, Sollwert, Status oder Rückmeldung mit Wertebereich und Bedeutung. Kein Kommunikationskanal.',
}


def catalog(arguments):
    from .catalog import TOOLS
    requested = arguments.get('capability_id')
    items = [deepcopy(item) for item in CAPABILITIES if not requested or item['id'] == requested]
    if not items:
        raise ValueError('Diese Fähigkeit ist nicht registriert.')
    state = WorkflowStatusService(current_project_id()).get(summary=True)
    settings = (state.get('context') or {}).get('engineering_wizard_settings') or {}
    for item in items:
        item['available'] = all(name in TOOLS for name in item['tools'])
        item['action'] = {'type': 'CAPABILITY', 'capability_id': item['id'], 'label': item['label'],
                          'description': item['description'], 'project_id': current_project_id()}
    return {'project_id': current_project_id(), 'project_name': settings.get('project_name') or current_project_id(),
            'capabilities': items}


def prepare_action(arguments):
    result = catalog(arguments)
    item = result['capabilities'][0]
    if not item['available']:
        raise ValueError('Die benötigten Fachwerkzeuge sind nicht verfügbar.')
    return {'agent_response': {'type': 'RESULT', 'status': 'ANSWERED',
            'text': item['description'], 'actions': [item['action']]}}


def repair_preview(_):
    from ..communication_repair import load_plan, public_plan, complete_plan
    planner, _ = load_plan()
    result = public_plan(complete_plan(planner))
    result['project_id'] = current_project_id()
    return result


def structure_preview(arguments):
    from ..structure_transfer import analyze_ecu_transfer
    return analyze_ecu_transfer({'source_hardware_id': arguments['source_hardware_id'],
                                 'target_hardware_ids': arguments['target_hardware_ids']})


def structure_evaluate(arguments):
    from ..structure import evaluate_structure
    return {'analysis': evaluate_structure({'selections': arguments['selection']})}


def duplicates_preview(_):
    from ..structure_transfer import analyze_system_duplicates
    return analyze_system_duplicates()


def fault_proposals(_):
    from ..simulation import propose_faults
    return {'items': propose_faults(), 'review': 'simulation-fault-proposals'}
