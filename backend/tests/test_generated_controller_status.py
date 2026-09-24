from backend.engineering.agent_tools import generation
from backend.engineering.device_communication import ECU_STATES, communication_findings


def test_explicit_new_acquisition_ecu_uses_reviewable_project_evidence(monkeypatch):
    nodes = [
        {'id': 'actuator', 'name': 'Stellglied1', 'device_type': 'ActuatorController'},
        {'id': 'controller', 'name': 'Controller', 'device_type': 'EmbeddedController'},
    ]
    interfaces = [
        {'id': 'actuator-port', 'hardware_node_id': 'actuator', 'interface_type': 'CAN'},
        {'id': 'controller-port', 'hardware_node_id': 'controller', 'interface_type': 'CAN'},
    ]
    messages = [{'interface_id': 'controller-port', 'cycle_ms': 10, 'configuration': {'generation_role': 'DEVICE_STATUS'}}]
    monkeypatch.setattr(generation, 'list_objects', lambda kind, **_: {
        'HardwareNode': nodes, 'Interface': interfaces, 'Message': messages}[kind])
    monkeypatch.setattr(generation, 'expand', lambda _: {'functions': [{'name': 'StellgliedpositionenAbfragen'}],
        'assumptions': [], 'interpretation': 'Periodische Stellgliedabfrage'})
    monkeypatch.setattr(generation.proposals, 'create', lambda kind, changes, prompt, **kwargs:
        {'kind': kind, 'changes': changes, **kwargs})
    result = generation.functions({'prompt': 'Lege eine ECU an, die mir die Stellgliedpositionen im System alle 30 Sekunden abfragt.'})
    assert result['kind'] == 'FUNCTION_STRUCTURE'
    assert next(change['data']['name'] for change in result['changes'] if change['object_type'] == 'HardwareNode') == 'StellgliedAbfrageECU'
    status = next(change for change in result['changes'] if change['object_type'] == 'Message')
    assert status['data']['cycle_ms'] == 10
    assert any('30-Sekunden-Abfragezyklus ist davon unabhängig' in note for note in result['assumptions'])
    assert any('vor Übernahme prüfen' in note for note in result['assumptions'])


def test_canopen_position_poll_draft_pairs_existing_devices_without_inventing_encoding(monkeypatch):
    nodes = [
        {'name': 'Positionssensor1', 'device_type': 'SensorController'},
        {'name': 'Positionssensor2', 'device_type': 'SensorController'},
        {'name': 'Servoantrieb1', 'device_type': 'ActuatorController'},
        {'name': 'Servoantrieb2', 'device_type': 'ActuatorController'},
    ]
    monkeypatch.setattr(generation, 'list_objects', lambda kind, **_: nodes if kind == 'HardwareNode' else [])
    notes, evidence = generation._position_poll_draft(
        'Lege eine ECU an, die Stellgliedpositionen alle 30 Sekunden abfragt.', 'CANopen')
    assert evidence['pairs'] == [
        {'sensor': 'Positionssensor1', 'actuator': 'Servoantrieb1'},
        {'sensor': 'Positionssensor2', 'actuator': 'Servoantrieb2'},
    ]
    assert evidence['interval_ms'] == 30000 and evidence['mode'] == 'REQUEST_RESPONSE'
    assert evidence['object_dictionary'] is None and evidence['encoding'] is None
    assert any('Objektverzeichnis' in note for note in notes)


def test_camera_and_function_generators_share_the_wizard_status_contract(monkeypatch):
    monkeypatch.setattr(generation.proposals, 'create', lambda kind, changes, *args, **kwargs: changes)
    for changes in [generation.functions({'prompt': 'Erzeuge 1 Funktion zur Temperaturüberwachung.',
                                          'new_hardware': {'name': 'ThermalController', 'device_type': 'EmbeddedController'},
                                          'status_technology': 'Ethernet', 'status_cycle_ms': 100}),
                    generation.camera_architecture({'coverage': 'surround', 'profile': 'four_wide', 'outputs': ['status']})]:
        graph = {kind: {} for kind in ('HardwareNode', 'Function', 'Interface', 'Message', 'Signal')}
        for change in changes:
            kind = change['object_type']
            if kind in graph:
                key = '$' + change['local_ref']
                graph[kind][key] = {**change['data'], 'id': key}
        assert not communication_findings(graph)
        assert len(graph['Signal']) == len(graph['HardwareNode'])
        for signal in graph['Signal'].values():
            assert signal['data']['enum_values'] == ECU_STATES
            assert signal['configuration']['template'] == 'canonical-device-status-v1'
            assert signal['length_bits'] == 4
            assert signal['semantic']['meaning'] == 'Betriebszustand'
