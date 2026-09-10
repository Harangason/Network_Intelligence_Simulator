from copy import deepcopy

from backend.engineering.routing.endpoint_consistency import align_receive_interfaces
from backend.knowledge.semantic_vocabulary import engineering_tokens, engineering_phrase_match, EngineeringSemanticVocabulary
from backend.tests.test_routing import FakeValidator, route_payload, SOURCE, TARGET, SOURCE_INTERFACE, TARGET_INTERFACE, SOURCE_PORT, TARGET_PORT


def test_physical_lin_port_does_not_mask_stale_logical_can_interface():
    class Validator(FakeValidator):
        def _rows(self, table, ids):
            rows = super()._rows(table, ids)
            if table == 'engineering_hardware_interfaces':
                for row in rows.values():
                    row['technology'] = 'LIN'
                    row['network_ref'] = 'lin-bus'
            return rows
    route = route_payload()
    route['source'].update(protocol='LIN', port_id=SOURCE_PORT, network_id='lin-bus')
    route['destinations'][0].update(protocol='LIN', port_id=TARGET_PORT, network_id='lin-bus')
    validation = Validator(source_type='LIN', target_type='CAN_FD').validate(route)
    assert 'DESTINATION_LOGICAL_PROTOCOL_MISMATCH' in {item['code'] for item in validation['errors']}
    assert validation['valid'] is False


def test_receive_repair_uses_only_a_unique_compatible_interface_on_the_same_device():
    route = route_payload()
    route['destinations'][0].update(protocol='LIN', port_id=TARGET_PORT, network_id='bus')
    interfaces = [{'id': TARGET_INTERFACE, 'hardware_node_id': TARGET, 'interface_type': 'CAN_FD'},
                  {'id': 'lin', 'hardware_node_id': TARGET, 'interface_type': 'LIN'},
                  {'id': 'foreign', 'hardware_node_id': SOURCE, 'interface_type': 'LIN'}]
    ports = [{'id': TARGET_PORT, 'hardware_node_id': TARGET, 'technology': 'LIN'}]
    before = deepcopy(route)
    repaired = align_receive_interfaces(route, interfaces, ports)
    assert repaired['destinations'][0]['interface_id'] == 'lin'
    assert repaired['source'] == before['source']
    assert route == before
    interfaces.append({'id': 'another', 'hardware_node_id': TARGET, 'interface_type': 'LIN'})
    assert align_receive_interfaces(route, interfaces, ports) == route


def test_agent_retrieval_uses_compounds_and_distinct_semantic_domains():
    assert engineering_tokens('Fahrersitz') == ['fahrer', 'sitz']
    assert engineering_tokens('Fahrwerk') == ['fahrwerk']
    assert engineering_tokens('Dämpferregelung') == ['daempfer', 'regelung']
    assert engineering_tokens('EGRValvePosition') == ['egr', 'valve', 'position']
    assert not engineering_phrase_match('Radar', 'rad')
    assert not engineering_phrase_match('DriverSeat', 'drive')
    vocab = EngineeringSemanticVocabulary()
    assert 'domain:seat' in vocab.concept_weights('Fahrersitz')
    assert 'domain:chassis' not in vocab.concept_weights('Fahrersitz')
    assert 'domain:chassis' in vocab.concept_weights('FrontLeftSuspensionTravel')
    assert 'domain:exhaust' not in vocab.concept_weights('OilTemperature')


def test_owner_inference_separates_systems_and_preserves_confirmed_assignments():
    from backend.engineering.system_clusters import system_owners
    hardware = [{'id': name, 'name': name, 'device_type': 'ECU'} for name in
                ('Abgasnachbehandlung', 'Daempferregelung', 'Motorsteuerung', 'Fahrwerk', 'Fahrersitz')]
    hardware += [{'id': name, 'name': name, 'device_type': 'SensorController'} for name in
                 ('FrontLeftSuspensionTravel', 'OilTemperature', 'FahrersitzTemperatur')]
    owners = system_owners(hardware, {})
    assert owners['FrontLeftSuspensionTravel']['id'] == 'Daempferregelung'
    assert owners['OilTemperature']['id'] == 'Motorsteuerung'
    assert owners['FahrersitzTemperatur']['id'] == 'Fahrersitz'
    hardware[-3]['identity'] = {'system_owner_id': 'Fahrwerk', 'system_owner_source': 'network-editor'}
    assert system_owners(hardware, {})['FrontLeftSuspensionTravel']['id'] == 'Fahrwerk'
