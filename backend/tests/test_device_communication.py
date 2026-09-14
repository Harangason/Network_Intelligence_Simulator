from backend.engineering.device_communication import communication_findings, actuator_command_template, EXECUTION_STATES


def test_class_two_generation_adds_status_without_function_or_replacing_measurement():
    from backend.engineering.device_communication import complete_new_actuator_messages, ECU_STATES
    changes = [
        {'object_type': 'HardwareNode', 'local_ref': 'node', 'data': {'name': 'Smart', 'device_type': 'SensorController', 'device_class': 2}},
        {'object_type': 'Message', 'local_ref': 'msg', 'data': {'name': 'Measurement', 'dlc': 2, 'configuration': {'transport_unit': {'producer_ref': '$node'}}}},
        {'object_type': 'Signal', 'local_ref': 'value', 'data': {'name': 'Temperature', 'message_id': '$msg', 'start_bit': 0, 'length_bits': 8}},
    ]
    complete_new_actuator_messages(changes, {'HardwareNode': [], 'Message': [], 'Signal': []})
    status = next(c['data'] for c in changes if c['data']['name'] == 'SmartStatus')
    assert status['start_bit'] == 8
    assert status['data']['enum_values'] == ECU_STATES
    assert not any(c['object_type'] == 'Function' for c in changes)


def test_unknown_actuator_does_not_receive_an_invented_command():
    assert actuator_command_template({'name': 'AirbagIgniter'}) is None
    assert actuator_command_template({'name': 'TestSchaltausgang'})['length_bits'] == 1
    assert actuator_command_template({'name': 'TestStellglied'})['max_value'] == 100
    assert EXECUTION_STATES['ACCEPTED'] != EXECUTION_STATES['COMPLETED']


def test_minimum_model_checks_class_two_status_and_class_three_function():
    graph = {'HardwareNode': {
        'smart': {'id': 'smart', 'name': 'SmartSensor', 'device_type': 'SensorController', 'device_class': 2},
        'ecu': {'id': 'ecu', 'name': 'Engine', 'device_type': 'ECU', 'device_class': 3},
        'act': {'id': 'act', 'name': 'Actuator', 'device_type': 'ActuatorController', 'device_class': 1},
    }, 'Function': {}, 'Interface': {}, 'Message': {}, 'Signal': {}}
    findings = {(f['object_id'], f['code']) for f in communication_findings(graph)}
    assert ('smart', 'DEVICE_STATUS_MISSING') in findings
    assert ('smart', 'FUNCTION_MISSING') not in findings
    assert ('ecu', 'FUNCTION_MISSING') in findings
    assert ('act', 'ACTUATOR_FEEDBACK_MISSING') in findings


def test_empty_command_is_reported_at_model_review():
    message = {'id': 'command', 'name': 'Command', 'configuration': {'transport_unit': {'provenance': {'generator': 'wizard-local-actuator-command'}}}}
    graph = {'Message': {'command': message}}
    assert communication_findings(graph)[0]['code'] == 'COMMAND_SIGNALS_MISSING'
    graph['Signal'] = {'signal': {'id': 'signal', 'message_id': 'command'}}
    assert communication_findings(graph) == []


def test_explicit_generated_actuator_encoding_survives_model_boundary():
    from backend.engineering.device_communication import complete_new_actuator_messages
    definition = {'source': 'wizard-generic-actuator-v1', 'length_bits': 10, 'data_type': 'unsigned', 'unit': '%', 'factor': 0.1, 'min_value': 0, 'max_value': 100}
    changes = [
        {'object_type': 'HardwareNode', 'local_ref': 'act', 'data': {'name': 'DrivePrimaryCommand', 'device_type': 'ActuatorController', 'identity': {'actuator_command_template': definition}}},
        {'object_type': 'Message', 'local_ref': 'command', 'data': {'name': 'Drive command', 'dlc': 1, 'configuration': {'transport_unit': {'consumer_refs': ['$act'], 'provenance': {'generator': 'wizard-local-actuator-command'}}}}},
    ]
    complete_new_actuator_messages(changes, {'HardwareNode': [], 'Message': [], 'Signal': []})
    signal = next(c['data'] for c in changes if c['object_type'] == 'Signal')
    assert signal['length_bits'] == 10 and signal['factor'] == 0.1 and signal['max_value'] == 100
    assert changes[1]['data']['dlc'] == 2
    assert actuator_command_template({'name': 'DrivePrimaryCommand'}) is None
