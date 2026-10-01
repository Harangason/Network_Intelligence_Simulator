"""Pure regressions for wizard routing; every database boundary is replaced."""
from copy import deepcopy
from contextlib import contextmanager
import json

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.routing.generation import RoutingGenerationService
from backend.engineering.agent_tools import wizard_generation
from backend.tests.test_routing import (
    FakeValidator, route_payload, MESSAGE, SIGNAL, SOURCE, TARGET,
    SOURCE_INTERFACE, TARGET_INTERFACE, OTHER_SOURCE_INTERFACE, GATEWAY,
)


def endpoint_generator(monkeypatch):
    service = RoutingGenerationService()
    nodes = {SOURCE: {'id': SOURCE, 'name': 'Motor', 'device_type': 'ECU'},
             TARGET: {'id': TARGET, 'name': 'Kombiinstrument', 'device_type': 'ECU'}}
    interfaces = {SOURCE: [{'id': SOURCE_INTERFACE, 'interface_type': 'CAN_FD', 'hardware_node_id': SOURCE}],
                  TARGET: [{'id': TARGET_INTERFACE, 'interface_type': 'Ethernet', 'hardware_node_id': TARGET},
                           {'id': 'local-can', 'interface_type': 'CAN_FD', 'hardware_node_id': TARGET}]}
    ports = {SOURCE: [{'id': 'source-can', 'technology': 'CAN_FD', 'network_ref': 'drive'}],
             TARGET: [{'id': 'display-eth', 'technology': 'Ethernet', 'network_ref': 'display'},
                      {'id': 'display-local-can', 'technology': 'CAN_FD', 'network_ref': 'local-can'}]}
    candidate = {'nodes': [{'node_id': SOURCE}, {'node_id': GATEWAY}, {'node_id': TARGET}],
                 'gateways': [{'node_id': GATEWAY}], 'protocol': 'CAN_FD', 'score': 0.8,
                 'connections': [{'source_network_id': 'drive', 'target_network_id': 'drive'},
                                 {'source_network_id': 'display', 'target_network_id': 'display'}]}
    monkeypatch.setattr(service, '_node', lambda identifier: nodes[identifier])
    monkeypatch.setattr(service, '_interface_candidates', lambda identifier: deepcopy(interfaces[identifier]))
    monkeypatch.setattr(service, '_hardware_interface_candidates', lambda identifier: deepcopy(ports[identifier]))
    monkeypatch.setattr(service, 'find_candidate_paths', lambda *_: [deepcopy(candidate)])
    monkeypatch.setattr(service, '_message_context', lambda _: {'id': MESSAGE, 'hardware_node_id': SOURCE,
        'interface_id': SOURCE_INTERFACE, 'hardware_interface_id': 'source-can', 'cycle_ms': 10})
    monkeypatch.setattr('backend.engineering.routing.generation.RoutingValidator.validate',
                        lambda *_: {'valid': True, 'errors': []})
    return service, interfaces, ports, candidate


def test_gateway_receiver_logical_interface_follows_last_physical_segment(monkeypatch):
    service, *_ = endpoint_generator(monkeypatch)
    route = service.generate_route(source_node_id=SOURCE, destination_node_id=TARGET, message_id=MESSAGE)
    assert route['destinations'][0]['port_id'] == 'display-eth'
    assert route['destinations'][0]['protocol'] == 'ETHERNET'
    assert route['destinations'][0]['interface_id'] == TARGET_INTERFACE


def test_source_message_binding_wins_over_unrelated_relation_interface(monkeypatch):
    service, interfaces, _, candidate = endpoint_generator(monkeypatch)
    interfaces[SOURCE].append({'id': OTHER_SOURCE_INTERFACE, 'interface_type': 'LIN', 'hardware_node_id': SOURCE})
    candidate['connections'][0]['source_interface_id'] = OTHER_SOURCE_INTERFACE
    route = service.generate_route(source_node_id=SOURCE, destination_node_id=TARGET, message_id=MESSAGE)
    assert route['source']['interface_id'] == SOURCE_INTERFACE


def test_ambiguous_receiver_functions_require_an_explicit_choice(monkeypatch):
    service, interfaces, *_ = endpoint_generator(monkeypatch)
    interfaces[TARGET][0]['function_id'] = 'display-function'
    interfaces[TARGET].append({'id': 'another-ethernet', 'interface_type': 'Ethernet',
                               'hardware_node_id': TARGET, 'function_id': 'diagnostic-function'})
    with pytest.raises(EngineeringValidationError, match='mehrdeutig'):
        service.generate_route(source_node_id=SOURCE, destination_node_id=TARGET, message_id=MESSAGE)


def test_explicit_receiver_relation_selects_the_function_on_final_port(monkeypatch):
    service, interfaces, _, candidate = endpoint_generator(monkeypatch)
    interfaces[TARGET].append({'id': 'another-ethernet', 'interface_type': 'Ethernet', 'hardware_node_id': TARGET})
    candidate['connections'][-1]['target_interface_id'] = 'another-ethernet'
    route = service.generate_route(source_node_id=SOURCE, destination_node_id=TARGET, message_id=MESSAGE)
    assert route['destinations'][0]['interface_id'] == 'another-ethernet'


def test_same_protocol_local_and_backbone_interfaces_follow_canonical_port_binding(monkeypatch):
    service, interfaces, ports, candidate = endpoint_generator(monkeypatch)
    interfaces[TARGET][0].update(interface_type='CAN_FD', physical_interface_ids=['display-eth'])
    interfaces[TARGET][1]['physical_interface_ids'] = ['display-local-can']
    ports[TARGET][0]['technology'] = 'CAN_FD'
    route = service.generate_route(source_node_id=SOURCE, destination_node_id=TARGET, message_id=MESSAGE)
    assert route['destinations'][0]['interface_id'] == TARGET_INTERFACE


def test_declared_controller_endpoint_preserves_function_identity_among_calculated_outputs():
    controller = {'id': 'controller-endpoint', 'function_id': 'controller-function', 'interface_type': 'Ethernet',
                  'configuration': {'physical_interface_ids': ['backbone'], 'endpoint_role': 'SYSTEM_CONTROLLER'}}
    radio = {'id': 'radio-endpoint', 'function_id': 'radio-function', 'interface_type': 'Ethernet',
             'configuration': {'physical_interface_ids': ['backbone']}}
    assert RoutingGenerationService._logical_endpoint([radio, controller],
        {'id': 'backbone', 'technology': 'Ethernet'}) == controller
    assert RoutingGenerationService._logical_endpoint([radio, controller],
        {'id': 'backbone', 'technology': 'Ethernet'}, preferred_id='radio-endpoint') == radio


def test_gateway_own_status_uses_the_recipient_channel_without_reencoding():
    def change(kind, ref, **data):
        return {'object_type': kind, 'local_ref': ref, 'data': data}
    changes = [
        change('HardwareNode', 'gateway', name='Gateway', device_type='Gateway'),
        change('HardwareNode', 'display', name='Anzeige', device_type='ECU'),
        change('Function', 'gateway-function', hardware_node_id='$gateway'),
        change('HardwareNetworkInterface', 'gateway-can', hardware_node_id='$gateway', technology='CAN_FD', network_ref='drive'),
        change('HardwareNetworkInterface', 'gateway-eth', hardware_node_id='$gateway', technology='Ethernet', network_ref='display'),
        change('HardwareNetworkInterface', 'display-eth', hardware_node_id='$display', technology='Ethernet', network_ref='display'),
        change('Interface', 'gateway-can-logical', function_id='$gateway-function', interface_type='CAN_FD'),
        change('Interface', 'gateway-eth-logical', function_id='$gateway-function', interface_type='Ethernet'),
        change('Message', 'status', interface_id='$gateway-can-logical', hardware_interface_id='$gateway-can',
               dlc=1, cycle_ms=100, configuration={'transport_unit': {'consumer_refs': ['$display']},
               'communication_contract': {'role': 'DEVICE_STATUS', 'producer_ref': '$gateway', 'consumer_refs': ['$display']}}),
        change('Signal', 'state', message_id='$status', start_bit=0, length_bits=3, data_type='unsigned',
               data={'enum_values': {'OFF': 0, 'ACTIVE': 3, 'ERROR': 5}}),
    ]
    encoding = deepcopy(changes[-1])
    wizard_generation._bind_generated_gateway_status(changes, {})
    message = changes[-2]['data']
    assert message['interface_id'] == '$gateway-eth-logical' and message['hardware_interface_id'] == '$gateway-eth'
    assert message['dlc'] == 1 and message['cycle_ms'] == 100
    assert message['configuration']['communication_contract']['consumer_refs'] == ['$display']
    assert changes[-1] == encoding


def test_signal_subset_never_reduces_frame_dlc_or_load():
    validator = FakeValidator(signal_bits=1, message_bindings={MESSAGE: {'dlc': 64}})
    selected = validator.validate(route_payload())
    whole = validator.validate(route_payload(payload={'message_id': MESSAGE, 'signal_ids': []}))
    selected_load = next(row for row in selected['evidence'] if row['type'] == 'LOAD')
    whole_load = next(row for row in whole['evidence'] if row['type'] == 'LOAD')
    assert selected_load == whole_load
    assert selected_load['payload_bytes'] == 64


def test_signal_subset_does_not_bypass_classic_can_frame_limit():
    result = FakeValidator(signal_bits=1, source_type='CAN', target_type='CAN',
        message_bindings={MESSAGE: {'dlc': 64}}).validate(route_payload(
        source={'node_id': SOURCE, 'interface_id': SOURCE_INTERFACE, 'protocol': 'CAN'},
        destinations=[{'node_id': TARGET, 'interface_id': TARGET_INTERFACE, 'protocol': 'CAN'}]))
    assert any(row['code'] == 'PAYLOAD_TOO_LARGE' for row in result['errors'])


def test_gateway_output_frame_limit_is_checked_despite_translation_label():
    result = FakeValidator(signal_bits=1, target_type='LIN', gateway=True,
        message_bindings={MESSAGE: {'dlc': 64}}).validate(route_payload(
        destinations=[{'node_id': TARGET, 'interface_id': TARGET_INTERFACE, 'protocol': 'LIN'}],
        route={'hops': [SOURCE, GATEWAY, TARGET], 'gateways': [{'node_id': GATEWAY}],
               'transformations': [{'type': 'PROTOCOL_TRANSLATION', 'from_protocol': 'CAN_FD', 'to_protocol': 'LIN'}]}))
    assert any(row['code'] == 'PAYLOAD_TOO_LARGE' and 'LIN' in row['message'] for row in result['errors'])


def test_intermediate_gateway_segment_frame_limit_is_checked(monkeypatch):
    validator = FakeValidator(signal_bits=1, source_type='Ethernet', target_type='Ethernet', gateway=True,
                              message_bindings={MESSAGE: {'dlc': 64}})
    monkeypatch.setattr(validator, '_canonical_transport_segments', lambda *_: [
        {'network_id': 'backbone-a', 'protocol': 'ETHERNET'},
        {'network_id': 'gateway-can', 'protocol': 'CAN'},
        {'network_id': 'backbone-b', 'protocol': 'ETHERNET'}], raising=False)
    result = validator.validate(route_payload(
        source={'node_id': SOURCE, 'interface_id': SOURCE_INTERFACE, 'protocol': 'ETHERNET'},
        destinations=[{'node_id': TARGET, 'interface_id': TARGET_INTERFACE, 'protocol': 'ETHERNET'}],
        route={'hops': [SOURCE, GATEWAY, TARGET], 'gateways': [{'node_id': GATEWAY}],
               'transformations': [{'type': 'PROTOCOL_TRANSLATION'}]}))
    assert any(row['code'] == 'PAYLOAD_TOO_LARGE' and 'CAN' in row['message'] for row in result['errors'])


def test_canonical_multigateway_segments_are_resolved_from_actual_port_memberships(monkeypatch):
    gateway_b = '00000000-0000-0000-0000-000000000042'
    ports = [{'hardware_node_id': node, 'network_ref': network, 'technology': technology}
             for node, network, technology in [
                 (SOURCE, 'a', 'Ethernet'), (GATEWAY, 'a', 'Ethernet'),
                 (GATEWAY, 'middle', 'CAN'), (gateway_b, 'middle', 'CAN'),
                 (gateway_b, 'b', 'Ethernet'), (TARGET, 'b', 'Ethernet')]]
    class Connection:
        def execute(self, *_):
            return self
        def fetchall(self):
            return ports
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr('backend.engineering.routing.validation.get_connection', connection)
    validator = FakeValidator()
    validator.project_id = 'isolated-memory-project'
    segments = validator._canonical_transport_segments({'network_id': 'a'},
        [{'node_id': TARGET, 'network_id': 'b'}], {'hops': [SOURCE, GATEWAY, gateway_b, TARGET]})
    assert [(item['network_id'], item['protocol']) for item in segments] == [('a', 'ETHERNET'), ('middle', 'CAN'), ('b', 'ETHERNET')]


def test_multicast_shared_bus_is_one_physical_transmission():
    validator = FakeValidator(signal_bits=1, message_bindings={MESSAGE: {'dlc': 8}})
    source = {'node_id': SOURCE, 'interface_id': SOURCE_INTERFACE, 'network_id': 'shared', 'protocol': 'CAN_FD'}
    target = {'node_id': TARGET, 'interface_id': TARGET_INTERFACE, 'network_id': 'shared', 'protocol': 'CAN_FD'}
    single = validator.validate(route_payload(source=source, destinations=[target]))
    multicast = validator.validate(route_payload(source=source, destinations=[target, {**target, 'node_id': GATEWAY}],
        routing_policy={'routing_type': 'MULTICAST', 'redundancy': 'NONE'}))
    assert next(e for e in single['evidence'] if e['type'] == 'LOAD') == next(e for e in multicast['evidence'] if e['type'] == 'LOAD')


def test_independent_segment_loads_are_not_added_for_bus_saturation(monkeypatch):
    validator = FakeValidator(signal_bits=1, message_bindings={MESSAGE: {'dlc': 64}})
    monkeypatch.setattr(validator, '_canonical_transport_segments', lambda *_: [
        {'network_id': network, 'protocol': 'CAN_FD', 'bitrate': 2_000_000} for network in ('a', 'b', 'c')])
    result = validator.validate(route_payload(timing={'cycle_time_ms': 0.64}))
    assert not any(issue['code'] in {'BUS_LOAD_CRITICAL', 'BUS_LOAD_HIGH'}
                   for issue in [*result['errors'], *result['warnings']])
    load = next(item for item in result['evidence'] if item['type'] == 'LOAD')
    assert load['network_load_percent'] == {'a': 40.0, 'b': 40.0, 'c': 40.0}
    assert load['peak_segment_load_percent'] == 40.0
    assert load['route_load_percent'] == 120.0


def test_ui_notes_preserve_explicit_actuator_encoding():
    definition = '{"Valve":{"length_bits":2,"data_type":"unsigned","data":{"enum_values":{"CLOSE":0,"OPEN":3}}}}'
    direct = wizard_generation._confirmed_actuator_commands('- Aktor-Befehle: ' + definition)
    wrapped = wizard_generation._confirmed_actuator_commands('- Weitere Hinweise: - Aktor-Befehle: ' + definition)
    assert direct == wrapped == json.loads(definition)


def test_small_explicit_separate_gateway_message_is_valid_on_lin():
    # Repacking requires its own canonical message/encoding. Merely attaching a
    # translation label to the original large message is tested above and fails.
    validator = FakeValidator(signal_bits=1, source_type='LIN', target_type='LIN', message_bindings={MESSAGE: {'dlc': 1}})
    result = validator.validate(route_payload(
        source={'node_id': SOURCE, 'interface_id': SOURCE_INTERFACE, 'protocol': 'LIN'},
        destinations=[{'node_id': TARGET, 'interface_id': TARGET_INTERFACE, 'protocol': 'LIN'}]))
    assert result['valid'], result['errors']


def test_big_endian_signal_occupancy_does_not_inflate_the_canonical_frame(monkeypatch):
    validator = FakeValidator(signal_bits=8)
    rows = validator._rows
    def read_rows(table, ids):
        result = rows(table, ids)
        if table == 'engineering_signals':
            for item in result.values():
                item.update(start_bit=63, byte_order='big_endian')
        return result
    monkeypatch.setattr(validator, '_rows', read_rows)
    result = validator.validate(route_payload())
    assert result['valid'], result['errors']
    assert next(row for row in result['evidence'] if row['type'] == 'LOAD')['payload_bytes'] == 8


def identity(prompt, *, source=None, state=None, version='routing-test-v1'):
    return wizard_generation._proposal_identity('routing', prompt, source or {}, state or {}, version)


def test_resume_prose_does_not_change_the_request_identity():
    original = '- Lauf-ID: run-one\n- Systemcluster-Graph: []\nAufgabe: Fahrzeug'
    assert identity(original) == identity(original + '\nFortsetzung des bestätigten Wizard-Auftrags:\nJetzt das Routing prüfen.')


def test_identity_changes_for_logical_model_revision_and_generator_version():
    first = identity('request', source={'Interface': [{'id': 'i', 'version': 1}]})
    assert first != identity('request', source={'Interface': [{'id': 'i', 'version': 2}]})
    assert first != identity('request', source={'Interface': [{'id': 'i', 'version': 1}]}, version='routing-test-v2')


def test_request_identity_ignores_runtime_status_but_includes_request_revision():
    request = {'version': 2, 'run_id': 'one', 'revision': 1, 'prompt': 'immutable request', 'target': 'routing'}
    first = identity('immutable request', state={'context': {'wizard_request': request, 'agent_execution': {'state': 'RUNNING'}}})
    assert first == identity('immutable request', state={'context': {'wizard_request': request, 'agent_execution': {'state': 'BLOCKED'}}})
    assert first != identity('immutable request', state={'context': {'wizard_request': {**request, 'revision': 2}}})


def test_unchanged_invalid_proposal_keeps_findings_and_new_revision_replaces_it(monkeypatch):
    original = identity('request', source={'Interface': [{'id': 'i', 'version': 1}]})
    updated = identity('request', source={'Interface': [{'id': 'i', 'version': 2}]})
    row = {'proposal_type': 'WIZARD_ROUTING', 'proposal_id': 'old', 'evidence': [original],
           'engineering_contract': {'status': 'PROPOSED', 'validation_result': {'valid': False,
               'findings': [{'code': 'DESTINATION_LOGICAL_PROTOCOL_MISMATCH'}]}}}
    monkeypatch.setattr(wizard_generation.proposal_service, 'envelope', lambda item: item)
    assert wizard_generation._reusable_proposal('WIZARD_ROUTING', original, [row]) is row
    assert wizard_generation._reusable_proposal('WIZARD_ROUTING', updated, [row]) is None
    replaced = []
    monkeypatch.setattr(wizard_generation.proposal_service, 'set_replacement', lambda old, new: replaced.append((old, new)))
    wizard_generation._supersede_previous('WIZARD_ROUTING', updated, [row], {'proposal_id': 'new'})
    assert replaced == [('old', 'new')]


def test_amended_request_is_a_new_fingerprint_in_the_same_run_replacement_family():
    request = {'version': 2, 'run_id': 'run-one', 'revision': 1, 'prompt': 'old request', 'target': 'routing'}
    original = identity('old request', state={'context': {'wizard_request': request}})
    amended = identity('new request', state={'context': {'wizard_request': {**request, 'revision': 2, 'prompt': 'new request'}}})
    assert original['operation_key'] == amended['operation_key']
    assert original['prompt_sha256'] != amended['prompt_sha256']
    independent = identity('old request', state={'context': {'wizard_request': {**request, 'run_id': 'run-two'}}})
    assert independent['operation_key'] != original['operation_key']


def test_routing_findings_remain_structured_and_count_invalid_routes_not_messages(monkeypatch):
    from backend.engineering.agent_tools import proposal_service
    monkeypatch.setattr(proposal_service.RoutingValidator, 'validate', lambda *_: {'valid': False, 'errors': [
        {'code': 'DESTINATION_LOGICAL_PROTOCOL_MISMATCH', 'message': 'Kombiinstrument: CAN-FD passt nicht zu Ethernet.'},
        {'code': 'PAYLOAD_TOO_LARGE', 'message': 'Nachricht überschreitet den Zielbus.'}]})
    result = proposal_service._validate_changes([{'object_type': 'RoutingEntry', 'action': 'CREATE',
        'local_ref': 'route-one', 'data': route_payload()}])
    assert result['valid_count'] == 0 and len(result['findings']) == 2
    assert result['findings'][0]['code'] == 'DESTINATION_LOGICAL_PROTOCOL_MISMATCH'
    assert result['findings'][0]['object_ref'] == 'route-one'
    assert result['findings'][0]['index'] == 0
    assert result['findings'][0]['source']['node_id'] == SOURCE
