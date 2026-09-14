"""MCP adapters. Authority is loaded from the journal, never from tool arguments."""
from pydantic import Field
from backend.agent_core.api.tool_contract import Permission as P
from ..agent_tools.catalog import register, TEXT, ID
from .graph import ModelGraphService
from .models import GoalType, COMPLETION_CONTRACTS
from .ports import inspect_port_decision
from . import service


def result(goal):
    return {'workload_id': goal['workload_id'], 'status': goal['status'], 'agent_response': service.presentation(goal)}


def execution_result(goal):
    if goal['status'] in {'FOLLOWUP_PENDING', 'SIMULATION_RUNNING'}:
        from .followups import advance
        return advance(goal, result)
    return result(goal)


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
