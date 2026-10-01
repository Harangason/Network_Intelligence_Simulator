"""MCP adapters. Authority is loaded from the journal, never from tool arguments."""
from pydantic import Field
from backend.agent_core.api.tool_contract import Permission as P
from ..agent_tools.catalog import register, TEXT, ID
from .graph import ModelGraphService
from .models import GoalType, COMPLETION_CONTRACTS
from .ports import inspect_port_decision
from . import service


def result(goal):
    from .outputs import ensure_outputs
    if goal['status'] != 'OUTPUT_PENDING':
        goal = ensure_outputs(goal)
    return {'workload_id': goal['workload_id'], 'status': goal['status'], 'agent_response': service.presentation(goal)}


def execution_result(goal):
    if goal['status'] in {'FOLLOWUP_PENDING', 'SIMULATION_RUNNING'}:
        from .followups import advance
        return advance(goal, result)
    return result(goal)


def type_input(arguments):
    from .typing import type_reference
    graph = ModelGraphService.load()
    return type_reference(graph, arguments['reference']).model_dump(mode='json')


def connectivity(arguments):
    graph = ModelGraphService.load()
    items = []
    for ref in arguments['references']:
        obj = graph.find_object(ref)
        host = graph.host(str(obj['id']))
        ports = graph.find_hardware_interfaces(str(host['id']))
        items.append({'object': obj, 'hardware': host, 'ports': ports,
                      'networks': [graph.networks[n] for n in graph.find_network_membership(str(host['id'])) if n in graph.networks]})
    return {'items': items, 'model_revision': graph.revision}


def communication_feasibility(arguments):
    from .planner import connection_plan
    graph = ModelGraphService.load()
    plan = connection_plan(graph, 'Kommunikationsmöglichkeit prüfen', arguments['source_ref'], arguments['target_ref'])
    return {'model_revision': graph.revision, 'status': plan['status'],
            'findings': plan.get('findings', []), 'data_gaps': plan.get('data_gaps', []),
            'pending_decision': plan.get('pending_decision'),
            'strategies': plan.get('strategies', []), 'read_only': True,
            'functional_acceptance': 'UNVERIFIED'}

register('inspect_communication_feasibility', 'Kommunikationsmöglichkeit zwischen vorhandenen Objekten prüfen. Keine Änderungen, Freigaben oder Simulation.',
         P.READ_MODEL, communication_feasibility, source_ref=TEXT, target_ref=TEXT)


def inspect_signal_definition(arguments):
    from ..signal_audit import inspect_signal, required_signal_bits
    graph = ModelGraphService.load()
    obj = graph.find_object(arguments['reference'])
    if str(obj['id']) not in graph.signals:
        raise ValueError('Das ausgewählte Objekt ist kein Signal.')
    message = graph.messages.get(str(obj.get('message_id')))
    return {'signal': obj, 'required_bits': required_signal_bits(obj),
            'validation': inspect_signal(obj, message), 'model_revision': graph.revision}


register('inspect_object_connectivity', 'Vorhandene Objekt-, Hardware-, Anschluss- und Netzzuordnungen lesen. Keine Berechnung oder Mutation.',
         P.READ_MODEL, connectivity, references=(list[str], Field(min_length=1, max_length=50)))
register('inspect_signal_definition', 'Vorhandenes kanonisches Signal auf Encoding und Bitbedarf prüfen, ohne neue Signale zu erzeugen.',
         P.READ_MODEL, inspect_signal_definition, reference=TEXT)


def assess_saved_finding(arguments):
    from ..agent_tools import conversation
    state = conversation.inspect()
    graph = ModelGraphService.load()
    obj = graph.find_object(arguments['reference'])
    matches = []
    for identifier, finding in state.get('findings', {}).items():
        text = str(finding)
        if arguments['code'] in text and (str(obj['id']) in text or obj['name'] in text or arguments['reference'] in text):
            matches.append({'finding_id': identifier, 'finding': finding,
                            'decision': state.get('decisions', {}).get(identifier, {'status': 'OPEN'})})
    return {'items': matches, 'object': obj, 'model_revision': graph.revision}


register('inspect_saved_finding', 'Gespeicherten Befund und Entscheidungsstatus anhand Code und kanonischem Objekt lesen. Keine Risikoakzeptanz ableiten.',
         P.READ_MODEL, assess_saved_finding, code=TEXT, reference=TEXT)


register('type_engineering_input', 'Fachlichen Objekttyp aus kanonischer ID, Name oder Alias ermitteln. Mehrdeutigkeit bleibt offen; erzeugt keine Objekte.',
    P.READ_MODEL, type_input, reference=TEXT)


register('inspect_model_situation', 'Aktuelles kanonisches Modell einschließlich Hardwarefähigkeiten, Controller, Ports, Netze, Routing und Abhängigkeiten lesen.', P.READ_MODEL,
    lambda a: ModelGraphService.load().situation(a['target_refs']).model_dump(mode='json'), target_refs=(list[str], Field(default_factory=list, max_length=50)))
register('inspect_communication_capability', 'Explizit bestätigte Kommunikationsfähigkeiten einer Hardware lesen; keine Controller oder Ports daraus erfinden.', P.READ_MODEL,
    lambda a: {'capabilities': ModelGraphService.load().find_communication_capabilities(a['hardware_ref'])}, hardware_ref=ID)
register('inspect_controller_capacity', 'Controllergrenzen und tatsächlich belegte Kanäle prüfen.', P.READ_MODEL,
    lambda a: ModelGraphService.load().find_port_capacity(a['controller_ref']), controller_ref=ID)
register('find_free_port', 'Vorhandene freie physische Anschlüsse finden.', P.READ_MODEL,
    lambda a: {'ports': ModelGraphService.load().find_free_ports(a['hardware_ref'], a['technology'])}, hardware_ref=ID, technology=TEXT)
register('find_free_channel', 'Freie, bestätigte Controllerkanäle finden.', P.READ_MODEL,
    lambda a: {'channels': ModelGraphService.load().find_free_channels(a['controller_ref'])}, controller_ref=ID)
register('inspect_port_decision', 'Anschluss wiederverwenden, gezielt anlegen oder Hardwaregrenze melden. Nur technisch mögliche Optionen anbieten.', P.READ_MODEL,
    lambda a: inspect_port_decision(ModelGraphService.load(), a['hardware_ref'], a['technology'], a['network_ref']), hardware_ref=ID, technology=TEXT, network_ref=TEXT)
register('validate_port_connection', 'Port, HardwareInterface, Technologie und Netzmitgliedschaft zusammen prüfen.', P.READ_MODEL,
    lambda a: {'findings': ModelGraphService.load().can_connect_port(a['port_ref'], a['network_ref'])}, port_ref=TEXT, network_ref=TEXT)
register('prepare_engineering_connection', 'Funktionspartner anhand ihrer aktuellen Hardware planen. Vollständigen Ausführungsplan mit gezielter Anschlussentscheidung speichern.', P.GENERATE_PROPOSAL,
    lambda a: execution_result(service.prepare(a['goal'], a['source_ref'], a['target_ref'], a['message_ids'])), goal=TEXT, source_ref=TEXT, target_ref=TEXT, message_ids=(list[str], Field(default_factory=list, max_length=100)))
register('continue_engineering_goal', 'Bestehenden Auftrag nach einer serverseitig gespeicherten Nutzerentscheidung vollständig ausführen. Ohne Freigabe keine Modelländerung.', P.EXECUTE_AUTHORIZED_GOAL,
    lambda a: execution_result(service.resume(a['workload_id'])), workload_id=ID)

def execute_port_plan(arguments):
    goal = service.get_goal(arguments['workload_id'])
    if goal['status'] != 'COMPLETE' and not goal.get('authorization'):
        raise PermissionError('Zuerst den Anschlussplan durch eine gespeicherte Nutzerentscheidung freigeben.')
    return execution_result(service.resume(arguments['workload_id']))

for name in ('create_physical_port', 'create_hardware_interface', 'bind_port_to_interface', 'connect_port_to_network'):
    register(name, 'Den angegebenen Anschlussauftrag atomar bis einschließlich Port, Interface, Netzbindung, Routing und Validierung ausführen. '
        'Benötigt eine gespeicherte Nutzerfreigabe; einzelne unvollständige Portänderungen werden nicht veröffentlicht.',
        P.EXECUTE_AUTHORIZED_GOAL, execute_port_plan, workload_id=ID)
register('inspect_engineering_goal', 'Gespeicherten Auftrag, Fortschritt, Entscheidungen, Änderungen und Zielprüfung lesen.', P.READ_MODEL,
    lambda a: {**result(service.get_goal(a['workload_id'])), 'journal': service.get_goal(a['workload_id'])['journal']}, workload_id=ID)
register('inspect_goal_completion_contracts', 'Definierte Zielbedingungen der Engineering-Auftragsarten lesen. Ein Kriteriensatz allein belegt keinen implementierten Ausführungsadapter; Tool-Erfolg ist kein Zielnachweis.', P.READ_MODEL,
    lambda _: {kind.value: criteria for kind, criteria in COMPLETION_CONTRACTS.items()})
