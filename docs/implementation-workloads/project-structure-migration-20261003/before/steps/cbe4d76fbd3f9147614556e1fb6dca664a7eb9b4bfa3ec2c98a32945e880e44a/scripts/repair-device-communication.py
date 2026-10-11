"""Audit minimum communication and fill missing generated simulator templates only."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.agent_tools import model
from backend.engineering.device_communication import communication_findings, actuator_command_template, EXECUTION_STATES, ECU_STATES
from backend.engineering.db import RequestUnit, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.repository import create_object, update_object
from backend.engineering.message_packing import valid_payload_bytes

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
project = 'network-project-20260909082213746-780a13ef'
token = activate_project(project)
unit = RequestUnit(project)
try:
    graph = {kind: {str(row['id']): row for row in model.objects(kind)} for kind in
        ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal')}
    before = communication_findings(graph)
    planned = []
    normalized_states = []
    for sid, signal in graph['Signal'].items():
        message = graph['Message'].get(str(signal.get('message_id')), {})
        interface = graph['Interface'].get(str(message.get('interface_id')), {})
        owner_id = interface.get('hardware_node_id') or graph['Function'].get(str(interface.get('function_id')), {}).get('hardware_node_id')
        owner = graph['HardwareNode'].get(str(owner_id), {})
        values = (signal.get('data') or {}).get('enum_values') or {}
        legacy = values == {'OK': 0, 'WARNING': 1, 'ERROR': 2, 'NOT_AVAILABLE': 3} or values == {'OK': 0, 'DEGRADED': 1, 'ROUTING_LIMITED': 2, 'ERROR': 3}
        if int(owner.get('device_class') or 0) >= 3 and signal.get('source') == 'ai_generated' and int(signal.get('version') or 0) == 1 and str(signal.get('name')).endswith('Status') and legacy and int(signal.get('length_bits') or 0) >= 3:
            normalized_states.append(signal['name'])
            if args.apply:
                update_object('Signal', sid, {'semantic': {**(signal.get('semantic') or {}), 'semantic_type': 'STATE', 'meaning': 'Betriebszustand'},
                    'data': {**(signal.get('data') or {}), 'enum_values': ECU_STATES, 'allowed_values': list(ECU_STATES), 'default_value': 'OFF', 'reserved_values': [6], 'invalid_values': [7]},
                    'expected_version': signal['version']})
    for mid, message in graph['Message'].items():
        transport = (message.get('configuration') or {}).get('transport_unit') or {}
        command = (transport.get('provenance') or {}).get('generator') == 'wizard-local-actuator-command'
        current = [s for s in graph['Signal'].values() if str(s.get('message_id')) == mid]
        owner = graph['HardwareNode'].get(str(transport.get('producer_ref')), {})
        candidates = []
        if command and not current:
            for target in transport.get('consumer_refs') or []:
                actuator = graph['HardwareNode'].get(str(target), {})
                template = actuator_command_template(actuator)
                if template:
                    candidates.append({'name': actuator['name'] + 'Sollwert', **template})
        elif owner.get('device_type') == 'ActuatorController' and actuator_command_template(owner) and current:
            name = owner['name'] + 'Ausfuehrung'
            if not any(s['name'] == name for s in current):
                candidates.append({'name': name, 'length_bits': 3, 'data_type': 'unsigned', 'factor': 1, 'unit': 'code',
                    'min_value': 0, 'max_value': 4, 'semantic': {'semantic_type': 'STATE', 'meaning': 'Ausführung des angeforderten Befehls'},
                    'data': {'enum_values': EXECUTION_STATES, 'default_value': 'IDLE', 'invalid_values': [7], 'reserved_values': [5, 6]}})
        offset = max((int(s.get('start_bit') or 0) + int(s.get('length_bits') or 0) for s in current), default=0)
        for candidate in candidates:
            payload = {**candidate, 'message_id': mid, 'start_bit': offset, 'byte_order': 'little_endian', 'offset_value': 0,
                'source': 'ai_generated', 'configuration': {'generation_role': 'COMMAND' if command else 'EXECUTION_FEEDBACK',
                    'template': 'generic-simulation-actuator-v1', 'requires_hardware_adaptation': True}}
            planned.append({'message': message['name'], 'signal': candidate['name'], 'bits': candidate['length_bits']})
            offset += candidate['length_bits']
            if args.apply:
                create_object('Signal', payload)
        if candidates and (offset + 7) // 8 > int(message.get('dlc') or 0):
            logical = graph['Interface'].get(str(message.get('interface_id')), {})
            dlc = valid_payload_bytes(logical.get('interface_type', 'CAN_FD'), (offset + 7) // 8)
            if dlc is None:
                raise ValueError(f"{message['name']}: Payload passt nicht in die Nachricht")
            if args.apply:
                configuration = {**(message.get('configuration') or {})}
                configuration['transport_unit'] = {**transport, 'payload_size': dlc}
                update_object('Message', mid, {'dlc': dlc, 'configuration': configuration, 'expected_version': message['version']})
    after = communication_findings({kind: {str(row['id']): row for row in model.objects(kind)} for kind in graph}) if args.apply else before
    if args.apply:
        from backend.engineering.workflow.service import WorkflowStatusService
        if planned or normalized_states:
            WorkflowStatusService(project).mark_changed('engineering_model', 'Aktor-Kommunikation ergänzt und generierte ECU-Zustände vereinheitlicht.', actor='device-communication-repair')
        unit.finish(True)
    print(json.dumps({'applied': args.apply, 'changes': planned, 'normalized_states': normalized_states, 'before': before, 'after': after}, ensure_ascii=False, default=str))
finally:
    unit.close()
    reset_project(token)
    close_pool()
