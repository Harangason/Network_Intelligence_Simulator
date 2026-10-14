from copy import deepcopy
import json
from uuid import uuid4
import pytest

from backend.nis.engineering.communication.device_communication import (
    attach_functional_device_contracts, communication_findings,
)


def graph(domain='robotics'):
    nodes = {
        'sensor': {'id': 'sensor', 'name': 'Sensor1', 'device_type': 'SensorController', 'device_class': 1,
                   'identity': {'functional_device_contract': {'version': 1, 'role': 'SENSOR', 'measurement': 'image_frame', 'owner_ref': 'camera'}}},
        'camera': {'id': 'camera', 'name': 'CameraProcessing', 'device_type': 'IndustrialPC', 'device_class': 4,
                   'identity': {'functional_device_contract': {'version': 1, 'role': 'PERCEPTION', 'required_measurement': 'image_frame',
                               'input_refs': ['sensor'], 'output_signal': 'Objects'}}},
        'actuator': {'id': 'actuator', 'name': 'Valve', 'device_type': 'ActuatorController', 'device_class': 1,
                     'identity': {'functional_device_contract': {'version': 1, 'role': 'ACTUATOR', 'owner_ref': 'camera'}}},
    }
    messages = {name: {'id': name, 'interface_id': producer, 'direction': 'tx',
                      'configuration': {'transport_unit': {'producer_ref': producer, 'consumer_refs': receivers}}}
                for name, producer, receivers in [('raw', 'sensor', ['camera']), ('objects', 'camera', ['navigation']), ('command', 'camera', ['actuator'])]}
    return {'HardwareNode': nodes, 'Function': {'function': {'id': 'function', 'hardware_node_id': 'camera', 'domain': domain}},
            'Interface': {ref: {'id': ref, 'hardware_node_id': ref} for ref in nodes}, 'Message': messages,
            'Signal': {'image': {'id': 'image', 'name': 'Image', 'message_id': 'raw'},
                       'objects': {'id': 'objects', 'name': 'Objects', 'message_id': 'objects', 'configuration': {'structured_payload': {'version': 1}}},
                       'command': {'id': 'command', 'name': 'ValveCommand', 'message_id': 'command', 'configuration': {'generation_role': 'COMMAND'}},
                       'status': {'id': 'status', 'name': 'CameraStatus', 'message_id': 'command', 'semantic': {'meaning': 'Betriebszustand'}}}}


def codes(model):
    return {finding['code'] for finding in communication_findings(model)}


def test_functional_acceptance_is_industry_independent_and_requires_real_receptions():
    for domain in ('automotive', 'robotics', 'aerospace', 'building', 'custom'):
        model = graph(domain)
        assert not codes(model)
        model['Message']['raw']['configuration']['transport_unit']['consumer_refs'] = ['gateway']
        assert {'SENSOR_CONSUMER_MISSING', 'FUNCTION_INPUT_ROUTE_MISSING'} <= codes(model)


def test_status_and_actuator_feedback_cannot_replace_measurements_or_objects():
    model = graph()
    model['HardwareNode']['camera']['identity']['functional_device_contract']['input_refs'] = ['actuator']
    del model['Signal']['objects']
    assert {'FUNCTION_INPUT_MISSING', 'FUNCTION_OUTPUT_MISSING'} <= codes(model)
    model['Signal']['image']['configuration'] = {'generation_role': 'DEVICE_STATUS'}
    assert 'SENSOR_SEMANTICS_MISSING' in codes(model)


def test_radar_processing_requires_detections_or_tracks_not_scalar_distance():
    model = graph()
    sensor_contract = model['HardwareNode']['sensor']['identity']['functional_device_contract']
    processor_contract = model['HardwareNode']['camera']['identity']['functional_device_contract']
    processor_contract.update(required_measurement='object_list', accepted_measurements=['object_list', 'radar_detections', 'distance'])
    sensor_contract['measurement'] = 'distance'
    assert 'FUNCTION_INPUT_MISSING' in codes(model)
    sensor_contract['measurement'] = 'radar_detections'
    assert not codes(model)
    sensor_contract['measurements'] = ['distance', 'radar_detections']
    sensor_contract['measurement'] = 'distance'
    assert not codes(model)
    del sensor_contract['measurements']
    sensor_contract['measurement'] = 'temperature'
    assert 'FUNCTION_INPUT_MISSING' in codes(model)


def test_missing_object_consumer_and_actuator_command_are_reported():
    model = graph()
    model['Message']['objects']['configuration']['transport_unit']['consumer_refs'] = []
    del model['Message']['command']
    assert {'FUNCTION_CONSUMER_MISSING', 'ACTUATOR_COMMAND_MISSING'} <= codes(model)


@pytest.mark.parametrize('domain', ['automotive', 'robotics', 'aerospace', 'building', 'custom'])
def test_general_processor_requires_every_declared_input_not_one_status_route(domain):
    model = graph(domain)
    contract = model['HardwareNode']['camera']['identity']['functional_device_contract']
    contract.update(role='PROCESSOR', input_refs=['sensor', 'sensor2'])
    model['HardwareNode']['sensor2'] = {**deepcopy(model['HardwareNode']['sensor']), 'id': 'sensor2', 'name': 'SecondSensor'}
    assert 'FUNCTION_INPUT_ROUTE_MISSING' in codes(model)
    model['Interface']['sensor2'] = {'id': 'sensor2', 'hardware_node_id': 'sensor2'}
    model['Message']['raw2'] = {'id': 'raw2', 'interface_id': 'sensor2', 'direction': 'tx',
                              'configuration': {'transport_unit': {'consumer_refs': ['camera']}}}
    model['Signal']['value2'] = {'id': 'value2', 'name': 'SecondMeasurement', 'message_id': 'raw2'}
    assert not codes(model)
    model['Signal']['value2']['configuration'] = {'generation_role': 'DEVICE_STATUS'}
    assert 'FUNCTION_INPUT_ROUTE_MISSING' in codes(model)
    contract['input_refs'] = ['actuator', 'deleted-input']
    assert 'FUNCTION_INPUT_MISSING' in codes(model)


def test_processor_accepts_declared_function_output_from_another_processor():
    model = graph()
    model['HardwareNode']['navigation'] = {'id': 'navigation', 'name': 'Navigation', 'device_class': 1,
        'device_type': 'ECU', 'identity': {'functional_device_contract': {'version': 1, 'role': 'PROCESSOR', 'input_refs': ['camera']}}}
    assert not codes(model)
    model['Message']['objects']['configuration']['transport_unit']['consumer_refs'] = ['gateway']
    assert 'FUNCTION_INPUT_ROUTE_MISSING' in codes(model)


def test_legacy_audit_is_read_only_and_requires_review_without_reencoding():
    model = graph()
    for node in model['HardwareNode'].values():
        node['identity'].pop('functional_device_contract')
    original = deepcopy(model)
    assert not codes(model)  # Existing ordinary legacy validation stays compatible.
    findings = communication_findings(model, include_legacy=True)
    assert {f['object_id'] for f in findings if f['code'] == 'FUNCTIONAL_CONTRACT_REVIEW_REQUIRED'} == {'sensor', 'camera', 'actuator'}
    assert all(f['severity'] == 'REVIEW' for f in findings)
    assert model == original


def test_perception_and_sensor_status_routes_cannot_stand_in_for_measurement_delivery():
    model = graph()
    model['Message']['raw']['configuration']['transport_unit']['consumer_refs'] = []
    model['Signal']['sensor-status'] = {'id': 'sensor-status', 'name': 'Status', 'message_id': 'status-message',
                                      'configuration': {'generation_role': 'DEVICE_STATUS'}}
    model['Message']['status-message'] = {'id': 'status-message', 'interface_id': 'sensor',
                                        'configuration': {'transport_unit': {'consumer_refs': ['camera']}}}
    assert {'SENSOR_CONSUMER_MISSING', 'FUNCTION_INPUT_ROUTE_MISSING'} <= codes(model)
    model['Signal']['sensor-status']['configuration']['direct_signal_binding'] = {
        'source_hardware_node_ref': 'sensor', 'destination_hardware_node_ref': 'camera'}
    assert {'SENSOR_CONSUMER_MISSING', 'FUNCTION_INPUT_ROUTE_MISSING'} <= codes(model)


def test_measurement_or_feedback_is_not_an_actuator_command():
    model = graph()
    for role in ['MEASUREMENT', 'EXECUTION_FEEDBACK', 'DEVICE_STATUS']:
        model['Signal']['command']['configuration'] = {'generation_role': role}
        assert 'ACTUATOR_COMMAND_MISSING' in codes(model)
        model['Signal']['command']['configuration']['direct_signal_binding'] = {
            'source_hardware_node_ref': 'camera', 'destination_hardware_node_ref': 'actuator'}
        assert 'ACTUATOR_COMMAND_MISSING' in codes(model)
    model['Signal']['command']['configuration'] = {'generation_role': 'COMMAND'}
    assert not codes(model)


def test_functional_agent_validation_returns_frozen_project_revision_without_mutation(monkeypatch):
    from backend.nis.agent.tools import services, model as access
    state = {key: [] for key in access.SECTIONS}
    state.update(project_id='audit-project', routing=[], topology={}, parameters={})
    original = deepcopy(state)
    context = access.ProjectContext('audit-project', state)
    monkeypatch.setattr(access.ProjectRepository, 'context', lambda self: context)
    empty = services._communication_validation({})
    assert not empty.success and empty.data['mutation'] == 'NONE'
    state['hardware'].append({'id': 'sensor', 'name': 'Sensor1', 'device_type': 'SensorController', 'device_class': 1})
    context = access.ProjectContext('audit-project', state)
    result = services._communication_validation({})
    assert not result.success
    assert result.data['project_id'] == 'audit-project' and result.data['model_revision'] == context.revision
    assert 'FUNCTIONAL_CONTRACT_REVIEW_REQUIRED' in {f['code'] for f in result.findings}
    assert context.snapshot() == state
    assert original['hardware'] == []


def test_status_or_unrelated_sender_cannot_satisfy_an_actuator_command():
    model = graph()
    model['Signal']['command']['configuration'] = {'generation_role': 'DEVICE_STATUS'}
    assert 'ACTUATOR_COMMAND_MISSING' in codes(model)
    model['Signal']['command']['configuration'] = {'generation_role': 'COMMAND'}
    model['Message']['command']['interface_id'] = 'sensor'
    assert 'ACTUATOR_COMMAND_MISSING' in codes(model)


def test_contract_attachment_resolves_ids_and_never_rewrites_imported_nodes():
    changes = [{'object_type': 'HardwareNode', 'local_ref': 'camera', 'data': {'name': 'Camera', 'device_type': 'IndustrialPC'}},
               {'object_type': 'HardwareNode', 'action': 'UPDATE', 'object_id': 'old', 'data': {'name': 'OldCamera'}},
               {'object_type': 'Function', 'local_ref': 'processing', 'data': {'hardware_node_id': '$camera'}}]
    chains = [{'hardware_name': 'Camera', 'configuration': {'functional_device_contract': {
        'version': 1, 'role': 'PERCEPTION', 'input_names': ['Sensor1']}}}]
    original = deepcopy(changes)
    attach_functional_device_contracts(changes, chains, {'sensor1': '$sensor', 'camera': '$camera'}, enabled=False)
    assert changes == original
    attach_functional_device_contracts(changes, chains, {'sensor1': '$sensor', 'camera': '$camera'})
    assert 'input_refs' not in changes[0]['data']['identity']['functional_device_contract']
    assert changes[2]['data']['configuration']['functional_device_contract']['input_refs'] == ['$sensor']
    assert changes[1] == original[1]


def test_new_processor_inputs_come_from_explicit_function_outputs_not_shared_network_or_status():
    def proposal(scope='FUNCTION_OUTPUT', role='FUNCTION_OUTPUT'):
        return [
            {'object_type': 'HardwareNode', 'local_ref': 'nav', 'data': {'name': 'Navigator', 'device_type': 'ECU'}},
            {'object_type': 'Function', 'local_ref': 'nav-function', 'data': {'hardware_node_id': '$nav'}},
            {'object_type': 'Message', 'local_ref': 'object-message', 'data': {'name': 'Objects',
             'configuration': {'communication_contract': {'scope': scope},
                               'transport_unit': {'producer_ref': '$camera', 'consumer_refs': ['$nav']}}}},
            {'object_type': 'Signal', 'local_ref': 'objects', 'data': {'name': 'Objects', 'message_id': '$object-message',
             'configuration': {'generation_role': role}}},
        ]
    changes = proposal()
    attach_functional_device_contracts(changes, [], {}, enabled=True)
    contract = changes[1]['data']['configuration']['functional_device_contract']
    assert contract['role'] == 'PROCESSOR' and contract['input_refs'] == ['$camera']
    for scope, role in [('LOCAL_IO', 'MEASUREMENT'), ('FUNCTION_OUTPUT', 'DEVICE_STATUS')]:
        changes = proposal(scope, role)
        attach_functional_device_contracts(changes, [], {}, enabled=True)
        assert 'functional_device_contract' not in changes[0]['data'].get('identity', {})
        assert 'functional_device_contract' not in changes[1]['data'].get('configuration', {})


@pytest.mark.parametrize('industry,model_type', [('Custom', 'custom'), ('Robotics', 'robotics_ros')])
def test_real_generator_review_apply_preserves_functional_chain(industry, model_type):
    from backend.nis.agent.tools import wizard_generation, proposal_service, model
    from backend.nis.agent.tools.runtime import ToolAuthority, execute
    from backend.nis.agent.api.tool_contract import Permission
    authority = ToolAuthority('pytest-functional-chain-' + uuid4().hex)
    clusters = [{'network_id': 'ethernet', 'bus_name': 'Perception', 'controllers': [
        {'ecu': 'Kameraverarbeitung', 'sensors': ['Sensor1'], 'actuators': []},
        {'ecu': 'AutonomeNavigation', 'sensors': [], 'actuators': []}],
        'functional_routes': [{'source': 'Kameraverarbeitung', 'target': 'AutonomeNavigation',
                               'signals': ['KameraverarbeitungObjektdaten'], 'excluded_signals': []}]}]
    prompt = '\n'.join([
        '- Industrie: ' + industry, '- Projekt-Modelltyp: ' + model_type,
        '- Netzwerktechnologien: Ethernet (ethernet)',
        '- Hardware-Sollwerte: {"gateways":0,"ecus":2,"sensors":1,"actuators":0}',
        '- Geräteanschlüsse: {"Kameraverarbeitung":"Ethernet","AutonomeNavigation":"Ethernet","Sensor1":"Ethernet"}',
        '- Sensor-Messgrößen: {"Sensor1":"image_frame"}',
        '- Funktionaler Generierungsvertrag: sensor-actuator-v1',
        '- Systemcluster-Graph: ' + json.dumps(clusters),
        'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:',
        'Erstelle die bestätigte Kameraverarbeitung mit Bilddatensensor und autonomer Navigation.',
    ])

    def operation():
        proposal = wizard_generation.generate({'prompt': prompt})
        checked = proposal_service.validate(proposal['proposal_id'])
        assert checked['status'] == 'VALIDATED', json.dumps(checked['validation_result'], ensure_ascii=False)
        approved = proposal_service.review(checked['proposal_id'], revision=checked['revision'],
                                          decision='approve', actor='test-human', trace_id=uuid4().hex)
        proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=uuid4().hex)
        actual = {kind: {str(row['id']): row for row in model.objects(kind)} for kind in
                  ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal')}
        assert not communication_findings(actual)
        sensor = next(row for row in actual['HardwareNode'].values() if row['name'] == 'Sensor1')
        camera = next(row for row in actual['HardwareNode'].values() if row['name'] == 'Kameraverarbeitung')
        target = next(row for row in actual['HardwareNode'].values() if row['name'] == 'AutonomeNavigation')
        target_function = next(row for row in actual['Function'].values() if str(row['hardware_node_id']) == str(target['id']))
        assert target_function['configuration']['functional_device_contract']['role'] == 'PROCESSOR'
        assert target_function['configuration']['functional_device_contract']['input_refs'] == [str(camera['id'])]
        function = next(row for row in actual['Function'].values() if
                        (row.get('configuration') or {}).get('functional_device_contract'))
        assert function['configuration']['functional_device_contract']['input_refs'] == [str(sensor['id'])]
        output = next(row for row in actual['Signal'].values() if row['name'] == 'KameraverarbeitungObjektdaten')
        message = actual['Message'][str(output['message_id'])]
        assert message['dlc'] == 1168
        assert message['configuration']['transport_unit']['consumer_refs'] == [str(target['id'])]
        assert message['configuration']['transport_unit']['producer_ref'] == str(camera['id'])
        assert output['configuration']['structured_payload']['max_objects'] == 32
    result = execute(authority, 'test_functional_apply', Permission.GENERATE_PROPOSAL, {}, lambda _: operation())
    assert result.success, result
