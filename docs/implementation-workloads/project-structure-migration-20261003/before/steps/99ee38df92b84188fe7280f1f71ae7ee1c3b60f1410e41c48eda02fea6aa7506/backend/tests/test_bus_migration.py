from copy import deepcopy

import pytest

from backend.engineering.bus_migration import plan_bus_change
from backend.engineering.models import EngineeringValidationError
from backend.engineering.network_scene import short_bus_name, _path


def fixture():
    state = {'parameters': {'networks': [{'id': n, 'name': n, 'technology': 'lin', 'bitrate': 19200} for n in ['bus1', 'bus2']]},
             'topology': {'nodes': [{'id': 'ecu', 'ports': [
                 {'id': n, 'hardwareInterfaceId': n, 'physicalNetworkId': n, 'bus': 'lin', 'name': n} for n in ['bus1', 'bus2']]}], 'edges': [
                 {'id': n, 'physicalNetworkId': n, 'bus': 'lin', 'routingEntryId': 'r'} for n in ['bus1', 'bus2']]}}
    objects = {
        'HardwareNetworkInterface': [{'id': n, 'name': n, 'hardware_node_id': 'ecu', 'technology': 'LIN', 'network_ref': n, 'channel_index': i + 1} for i, n in enumerate(['bus1', 'bus2'])],
        'Interface': [{'id': 'logical', 'interface_type': 'LIN'}],
        'Message': [{'id': 'm', 'name': 'Befehl', 'interface_id': 'logical', 'hardware_interface_id': 'bus1', 'dlc': 2, 'message_id_hex': '0x12',
                     'configuration': {'physical_transmit_bindings': [{'hardware_interface_id': 'bus2', 'network_id': 'bus2'}], 'communication_contract': {'role': 'COMMAND'}}}],
        'Signal': [{'id': 's', 'message_id': 'm', 'protocol_bindings': [{'technology_binding_ref': 'lin', 'semantic_ref': 'semantic-s'}]}],
    }
    routes = [{'id': 'r', 'status': 'APPROVED', 'revision': 3, 'payload': {'message_ids': ['m']}, 'source': {'network_id': 'bus1'}}]
    return state, objects, routes


def test_change_expands_shared_transmission_without_changing_ids_or_semantics():
    state, objects, routes = fixture()
    before = deepcopy((state, objects, routes))
    result = plan_bus_change(state, objects, routes, 'bus1', 'can_fd')
    assert {n['id'] for n in result['preview']['networks']} == {'bus1', 'bus2'}
    assert result['preview']['messages'] == result['preview']['routes'] == 1
    assert {p['bus'] for p in result['topology']['nodes'][0]['ports']} == {'can_fd'}
    changes = {(kind, key): value for kind, key, value in result['changes']}
    assert changes['Interface', 'logical']['interface_type'] == 'CAN_FD'
    assert changes['Message', 'm']['configuration']['physical_transmit_bindings'] == objects['Message'][0]['configuration']['physical_transmit_bindings']
    assert changes['Message', 'm']['configuration']['communication_contract']['role'] == 'COMMAND'
    assert changes['Signal', 's']['protocol_bindings'] == [{'technology_binding_ref': 'can_fd', 'semantic_ref': 'semantic-s'}]
    assert before == (state, objects, routes)


def test_channel_allocation_keeps_existing_target_channels_unique():
    state, objects, routes = fixture()
    objects['HardwareNetworkInterface'].append({'id': 'untouched', 'hardware_node_id': 'ecu', 'technology': 'CAN_FD', 'channel_index': 1})
    result = plan_bus_change(state, objects, routes, 'bus1', 'can_fd')
    changes = [patch for kind, _, patch in result['changes'] if kind == 'HardwareNetworkInterface']
    assert {patch['channel_index'] for patch in changes} == {2, 3}


def test_bus_change_rebinds_receive_interface_without_changing_physical_identity():
    state, objects, routes = fixture()
    objects['HardwareNetworkInterface'].append({'id': 'receiver-port', 'name': 'bus1', 'hardware_node_id': 'receiver',
                                               'technology': 'LIN', 'network_ref': 'bus1', 'channel_index': 1})
    objects['Interface'].extend([
        {'id': 'receive-lin', 'hardware_node_id': 'receiver', 'interface_type': 'LIN'},
        {'id': 'receive-can', 'hardware_node_id': 'receiver', 'interface_type': 'CAN_FD'},
    ])
    routes[0]['destinations'] = [{'node_id': 'receiver', 'port_id': 'receiver-port',
                                 'interface_id': 'receive-lin', 'network_id': 'bus1', 'protocol': 'LIN'}]
    before = deepcopy(routes)
    planned = plan_bus_change(state, objects, routes, 'bus1', 'can_fd')['routes'][0]
    assert planned['destinations'][0] == {**before[0]['destinations'][0],
                                         'interface_id': 'receive-can', 'protocol': 'CAN_FD'}
    assert routes == before


def test_incompatible_payload_rejected_before_any_mutation():
    state, objects, routes = fixture()
    objects['Message'][0]['dlc'] = 64
    before = deepcopy(objects)
    with pytest.raises(EngineeringValidationError, match='64 Byte'):
        plan_bus_change(state, objects, routes, 'bus1', 'lin')
    assert before == objects


def test_preview_token_includes_canonical_changes_and_target():
    state, objects, routes = fixture()
    token = plan_bus_change(state, objects, routes, 'bus1', 'can_fd')['preview']['token']
    assert token == plan_bus_change(state, objects, routes, 'bus1', 'can_fd')['preview']['token']
    objects['Message'][0]['cycle_ms'] = 50
    assert token != plan_bus_change(state, objects, routes, 'bus1', 'can_fd')['preview']['token']


def test_migrated_bus_names_do_not_collide_with_existing_target_bus():
    state, objects, routes = fixture()
    key = 'Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01'
    for hwi in objects['HardwareNetworkInterface']:
        if hwi['network_ref'] == 'bus1':
            hwi['network_ref'] = key
    state['parameters']['networks'][0].update(id=key, name=key)
    state['parameters']['networks'].append({'id': 'Antriebsstrang_01-IO-abgasnachbehandlung-can-fd-S01', 'technology': 'can_fd'})
    preview = plan_bus_change(state, objects, routes, key, 'can_fd')['preview']
    assert next(n for n in preview['networks'] if n['id'] == key)['name'] == 'Abgasnachbehandlung CAN-FD 02'


@pytest.mark.parametrize('bus', ['can', 'can_fd', 'can_xl', 'lin', 'automotive_ethernet', 'flexray'])
def test_supported_bus_contracts(bus):
    state, objects, routes = fixture()
    result = plan_bus_change(state, objects, routes, 'bus1', bus)
    assert all(n['technology'] == bus and n['bitrate'] > 0 for n in result['networks'])


def test_short_labels_and_aligned_gateway_arrow_path():
    assert short_bus_name('Antriebsstrang_01-S02', '') == 'Antriebsstrang_02'
    assert short_bus_name('Antriebsstrang_01-S02', 'Mein Bus') == 'Mein Bus'
    assert short_bus_name('Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01', '', 'can_fd') == 'Abgasnachbehandlung CAN-FD 01'
    assert _path([{'x': 10, 'y': 10}, {'x': 10, 'y': 40}, {'x': 10, 'y': 40}]) == 'M 10 10 L 10 40'
