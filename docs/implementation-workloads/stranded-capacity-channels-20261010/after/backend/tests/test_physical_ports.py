"""Independent physical buses need real, reviewed and persistable channels."""
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.nis.engineering.network.physical_ports import materialize_physical_ports
from backend.nis.engineering.network.physical_ports import topology_port_findings


def test_local_io_does_not_steal_an_existing_backbone_channel():
    topology, hardware, interfaces = sample()
    interfaces[0]['network_ref'] = 'reviewed-backbone'
    before = deepcopy(interfaces[0])
    repaired, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    canonical = effective(interfaces, changes)
    assert next(row for row in canonical if row['id'] == before['id']) == before
    assert repaired['nodes'][0]['ports'][0]['hardwareInterfaceId'] != before['id']


def sample():
    hardware = [{'id': node, 'name': node, 'device_type': 'Gateway' if node == 'g' else 'ECU'} for node in ('a', 'g', 'b')]
    interfaces = [{'id': 'old-' + node, 'name': 'old-' + node, 'hardware_node_id': node, 'technology': 'Ethernet' if node == 'g' else 'CAN_FD',
                   'channel_index': 1, 'network_ref': 'System_1' if node == 'g' else ''} for node in ('a', 'g', 'b')]
    topology = {'nodes': [{'id': node, 'name': node, 'kind': 'gateway' if node == 'g' else 'ecu', 'engineeringId': node,
        'ports': [{'id': node + '-' + net, 'bus': 'can_fd', 'hardwareInterfaceId': 'old-' + node, 'engineeringId': 'old-' + node,
                   'physicalNetworkId': net} for net in (('CAN1', 'CAN2') if node == 'g' else ('CAN1',) if node == 'a' else ('CAN2',))]} for node in ('a', 'g', 'b')],
        'edges': [{'id': 'e1', 'source': 'a', 'sourcePort': 'a-CAN1', 'target': 'g', 'targetPort': 'g-CAN1', 'bus': 'can_fd', 'physicalNetworkId': 'CAN1', 'engineeringRelationId': 'r1'},
                  {'id': 'e2', 'source': 'g', 'sourcePort': 'g-CAN2', 'target': 'b', 'targetPort': 'b-CAN2', 'bus': 'can_fd', 'physicalNetworkId': 'CAN2', 'engineeringRelationId': 'r2'}]}
    return topology, hardware, interfaces


def effective(interfaces, changes):
    graph = {str(row['id']): deepcopy(row) for row in interfaces}
    for change in changes:
        if change['object_type'] == 'HardwareNetworkInterface':
            identifier = change.get('object_id') or '$' + change['local_ref']
            graph[identifier] = {**graph.get(identifier, {}), **change['data'], 'id': identifier}
    return list(graph.values())


def test_wrong_gateway_protocol_and_aliases_are_replaced_by_reviewable_channels():
    old, hardware, interfaces = sample()
    original = deepcopy(old)
    assert 'PHYSICAL_CHANNEL_TECHNOLOGY' in {row['code'] for row in topology_port_findings(old, hardware, interfaces)}
    topology, changes = materialize_physical_ports(old, hardware, interfaces, [{'id': 'System_1', 'technology': 'ETHERNET'}])
    assert old == original
    gateway = next(node for node in topology['nodes'] if node['engineeringId'] == 'g')
    assert len({port['hardwareInterfaceId'] for port in gateway['ports']}) == 2
    added = [change['data'] for change in changes if change['object_type'] == 'HardwareNetworkInterface' and change.get('action') != 'UPDATE']
    assert [row['technology'] for row in added] == ['CAN_FD', 'CAN_FD']
    assert {row['channel_index'] for row in added} == {1, 2}
    assert not topology_port_findings(topology, hardware, effective(interfaces, changes))
    # The same effective state is idempotent, including pre-apply $local_refs.
    again, repeated = materialize_physical_ports(topology, hardware, effective(interfaces, changes),
        [{'id': 'System_1', 'technology': 'ETHERNET'}, *[row['data'] for row in changes if row['object_type'] == 'Network']])
    assert not repeated
    assert again == topology


@pytest.mark.parametrize('fault,code', [('alias', 'PHYSICAL_CHANNEL_SHARED_NETWORKS'), ('owner', 'PHYSICAL_CHANNEL_OWNER'),
    ('channel', 'DUPLICATE_PHYSICAL_CHANNEL'), ('edge', 'EDGE_PORT_NETWORK')])
def test_invalid_physical_bindings_fail_closed(fault, code):
    topology, hardware, interfaces = sample()
    topology, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    canonical = effective(interfaces, changes)
    gateway = topology['nodes'][1]
    first = next(row for row in canonical if row['id'] == gateway['ports'][0]['hardwareInterfaceId'])
    second = next(row for row in canonical if row['id'] == gateway['ports'][1]['hardwareInterfaceId'])
    if fault == 'alias':
        gateway['ports'][1]['hardwareInterfaceId'] = first['id']
    elif fault == 'owner':
        first['hardware_node_id'] = 'a'
    elif fault == 'channel':
        second['channel_index'] = first['channel_index']
    else:
        topology['edges'][0]['physicalNetworkId'] = 'CAN2'
    assert code in {row['code'] for row in topology_port_findings(topology, hardware, canonical)}


def test_capacity_split_allocates_separate_gateway_channels_and_removes_obsolete_ports():
    from backend.nis.intelligence.engineering.intelligence.network_planning import split_topology_by_distribution
    topology, hardware, interfaces = sample()
    interfaces[1]['technology'] = 'CAN_FD'
    interfaces[1]['network_ref'] = ''
    gateway = topology['nodes'][1]
    gateway['ports'] = [gateway['ports'][0]]
    for node in topology['nodes']:
        for port in node['ports']:
            port['physicalNetworkId'] = 'shared'
    for index, edge in enumerate(topology['edges']):
        edge.update(physicalNetworkId='shared', routingEntryIds=['route-' + str(index)])
        if index == 1:
            edge['sourcePort'] = gateway['ports'][0]['id']
    topology, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    interfaces = effective(interfaces, changes)
    split, count = split_topology_by_distribution(topology, {'networks': [{'network_id': 'shared', 'decision': 'SPLIT_CURRENT_TECHNOLOGY',
        'segments': [{'name': 'split-1', 'route_ids': ['route-0']}, {'name': 'split-2', 'route_ids': ['route-1']}]}]})
    assert count == 2
    repaired, changes = materialize_physical_ports(split, hardware, interfaces, [{'id': 'shared', 'technology': 'CAN_FD'}])
    gateway = repaired['nodes'][1]
    assert len(gateway['ports']) == 2
    assert len({port['hardwareInterfaceId'] for port in gateway['ports']}) == 2
    assert {port['physicalNetworkId'] for port in gateway['ports']} == {'split-1', 'split-2'}
    assert not topology_port_findings(repaired, hardware, effective(interfaces, changes))


def test_capacity_split_preserves_ports_of_an_unrelated_isolated_gateway():
    topology, hardware, interfaces = sample()
    gateway = topology['nodes'][1]
    gateway['ports'] = [{
        'id': 'gateway-ethernet',
        'name': 'Gateway Ethernet',
        'bus': 'ethernet',
        'engineeringId': 'old-g',
        'hardwareInterfaceId': 'old-g',
        'physicalNetworkId': 'gateway-backbone',
    }]
    topology['edges'] = [topology['edges'][0]]
    topology['edges'][0].update(source='a', sourcePort='a-CAN1', target='b', targetPort='b-CAN2')
    topology['nodes'][2]['ports'][0]['physicalNetworkId'] = 'CAN1'

    repaired, _changes = materialize_physical_ports(
        topology,
        hardware,
        interfaces,
        [
            {'id': 'CAN1', 'technology': 'CAN_FD'},
            {'id': 'gateway-backbone', 'technology': 'Ethernet'},
        ],
    )

    isolated = next(node for node in repaired['nodes'] if node['engineeringId'] == 'g')
    assert len(isolated['ports']) == 1
    assert isolated['ports'][0]['id'] == 'gateway-ethernet'
    assert isolated['ports'][0]['physicalNetworkId'] == 'gateway-backbone'
    assert isolated['ports'][0]['hardwareInterfaceId']


@pytest.mark.parametrize('technology,bus', [('LIN', 'lin'), ('CAN_FD', 'can_fd'), ('Ethernet', 'ethernet')])
def test_split_channels_have_unique_names_under_their_hardware_without_renaming_existing_ports(technology, bus):
    topology, hardware, interfaces = sample()
    for row in interfaces:
        row.update(technology=technology, network_ref='original', name='Reviewed connector',
                   target_load_limit=40, warning_load_limit=60, hard_load_limit=90)
    for node in topology['nodes']:
        for port in node['ports']:
            port.update(bus=bus, name='Reviewed connector', nameSource='user')
    for edge in topology['edges']:
        edge['bus'] = bus
    before = deepcopy(interfaces)
    repaired, changes = materialize_physical_ports(topology, hardware, interfaces,
        [{'id': 'original', 'technology': technology}])
    canonical = effective(interfaces, changes)
    signatures = [(row['hardware_node_id'], row['name'].casefold()) for row in canonical]
    assert len(signatures) == len(set(signatures)), 'New independent channels must not copy their original connector name.'
    assert all(next(row for row in canonical if row['id'] == original['id']) == original for original in before)
    assert all((row['target_load_limit'], row['warning_load_limit'], row['hard_load_limit']) == (40, 60, 90) for row in canonical)
    assert not topology_port_findings(repaired, hardware, canonical)
    again, repeated = materialize_physical_ports(repaired, hardware, canonical,
        [{'id': 'original', 'technology': technology}, *[row['data'] for row in changes if row['object_type'] == 'Network']])
    assert repeated == []
    assert again == repaired


def test_malformed_topology_is_reported_instead_of_crashing_status_reads():
    assert {row['code'] for row in topology_port_findings({'nodes': [None], 'edges': ['broken']}, [], [])} == {
        'INVALID_TOPOLOGY_NODE', 'INVALID_TOPOLOGY_EDGE'}


def test_message_on_two_independent_channels_requires_explicit_transmit_bindings():
    from backend.nis.engineering.network.physical_ports import physical_transmit_changes
    topology, hardware, interfaces = sample()
    topology, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    for index, edge in enumerate(topology['edges']):
        edge['routingEntryIds'] = [f'route-{index}']
    routes = [{'id': f'route-{index}', 'approval_state': 'APPROVED', 'source': {'node_id': 'g'}, 'payload': {'message_id': 'm'}} for index in range(2)]
    message = {'id': 'm', 'hardware_interface_id': 'old-g', 'configuration': {'user_setting': True}}
    changes = physical_transmit_changes(topology, routes, [message])
    assert len(changes) == 1
    configuration = changes[0]['data']['configuration']
    assert configuration['user_setting'] is True
    assert len(configuration['physical_transmit_bindings']) == 2
    assert {row['network_id'] for row in configuration['physical_transmit_bindings']} == {'CAN1', 'CAN2'}
    assert changes[0]['data']['hardware_interface_id'] in {row['hardware_interface_id'] for row in configuration['physical_transmit_bindings']}
    assert not physical_transmit_changes(topology, routes, [{**message, **changes[0]['data']}])


@pytest.mark.parametrize('bus,technology', [('can_fd', 'CAN_FD'), ('lin', 'LIN'), ('ethernet', 'Ethernet'), ('modbus_rtu', 'MODBUS_RTU')])
def test_complete_split_move_reuses_reviewed_connector_and_keeps_message_sender(bus, technology):
    from backend.nis.intelligence.engineering.intelligence.network_planning import split_topology_by_distribution
    hardware = [{'id': key, 'name': key, 'device_type': 'ECU'} for key in ('source', 'receiver')]
    interfaces = [{'id': key + '-channel', 'name': key, 'hardware_node_id': key, 'technology': technology,
                   'channel_index': 1, 'physical_port_ref': key + '-connector', 'network_ref': 'old-bus'} for key in ('source', 'receiver')]
    before = {'nodes': [{'id': key, 'engineeringId': key, 'ports': [{'id': key + '-port', 'hardwareInterfaceId': key + '-channel',
                'bus': bus, 'physicalNetworkId': 'old-bus'}]} for key in ('source', 'receiver')],
              'edges': [{'id': 'wire', 'source': 'source', 'target': 'receiver', 'sourcePort': 'source-port',
                        'targetPort': 'receiver-port', 'bus': bus, 'physicalNetworkId': 'old-bus', 'routingEntryIds': ['route']}]}
    routes = [{'id': 'route', 'approval_state': 'APPROVED', 'source': {'node_id': 'source'}, 'payload': {'message_id': 'message'}}]
    message = {'id': 'message', 'hardware_interface_id': 'source-channel', 'configuration': {'encoding': 'authored'}}
    plan = {'networks': [{'network_id': 'old-bus', 'decision': 'SPLIT_CURRENT_TECHNOLOGY',
                         'segments': [{'name': 'new-bus', 'route_ids': ['route']}]}]}
    topology, count = split_topology_by_distribution(before, plan)
    assert count == 1
    original = deepcopy((before, topology, interfaces, message))
    repaired, changes = materialize_physical_ports(topology, hardware, interfaces,
        [{'id': 'old-bus', 'technology': technology}], previous_topology=before, routes=routes, messages=[message])
    canonical = effective(interfaces, changes)
    assert len(canonical) == 2, 'Moving one complete branch does not create spare hardware channels.'
    assert {p['hardwareInterfaceId'] for n in repaired['nodes'] for p in n['ports']} == {'source-channel', 'receiver-channel'}
    assert all(p['network_ref'] == 'new-bus' and p['channel_index'] == 1 for p in canonical)
    assert not topology_port_findings(repaired, hardware, canonical)
    assert (before, topology, interfaces, message) == original


def test_multichannel_rebind_preserves_active_primary_and_does_not_adopt_unapproved_sources():
    from backend.nis.engineering.network.physical_ports import physical_transmit_changes
    topology, hardware, interfaces = sample()
    topology, _ = materialize_physical_ports(topology, hardware, interfaces, [])
    for index, edge in enumerate(topology['edges']):
        edge['routingEntryIds'] = [f'route-{index}']
    primary = topology['nodes'][1]['ports'][1]['hardwareInterfaceId']
    routes = [{'id': f'route-{index}', 'approval_state': 'APPROVED', 'source': {'node_id': 'g'},
               'payload': {'message_id': 'm'}} for index in range(2)]
    message = {'id': 'm', 'hardware_interface_id': primary, 'configuration': {'user_setting': True}}
    change = physical_transmit_changes(topology, routes, [message])[0]
    assert change['data'].get('hardware_interface_id', primary) == primary
    assert len(change['data']['configuration']['physical_transmit_bindings']) == 2
    assert physical_transmit_changes(topology, [{**r, 'approval_state': 'PENDING'} for r in routes], [message]) == []


def test_complete_multibranch_split_reuses_one_original_channel_without_unused_inventory():
    from backend.nis.intelligence.engineering.intelligence.network_planning import split_topology_by_distribution
    topology, hardware, interfaces = sample()
    interfaces[1].update(technology='CAN_FD', network_ref='')
    topology['nodes'][1]['ports'] = [topology['nodes'][1]['ports'][0]]
    for node in topology['nodes']:
        for port in node['ports']:
            port['physicalNetworkId'] = 'shared'
    for index, edge in enumerate(topology['edges']):
        edge.update(physicalNetworkId='shared', routingEntryIds=[f'route-{index}'])
    topology['edges'][1]['sourcePort'] = topology['nodes'][1]['ports'][0]['id']
    before, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    interfaces = effective(interfaces, changes)
    original = before['nodes'][1]['ports'][0]['hardwareInterfaceId']
    split, _ = split_topology_by_distribution(before, {'networks': [{'network_id': 'shared',
        'decision': 'SPLIT_CURRENT_TECHNOLOGY', 'segments': [
            {'name': 'split-2', 'route_ids': ['route-0']}, {'name': 'split-1', 'route_ids': ['route-1']}]}]})
    repaired, changes = materialize_physical_ports(split, hardware, interfaces,
        [{'id': 'shared', 'technology': 'CAN_FD'}], previous_topology=before)
    canonical = effective(interfaces, changes)
    active = {p['hardwareInterfaceId'] for n in repaired['nodes'] for p in n['ports']}
    assert active == {p['id'] for p in canonical}, 'A complete split must not leave phantom hardware behind.'
    assert len(canonical) == 4, 'Two independent gateway branches need two channels, not three.'
    assert next(p for p in canonical if p['id'] == original)['network_ref'] == 'split-1'


def test_logical_interface_reconciles_reviewed_multichannel_senders_and_preserves_unrelated_configuration():
    from backend.nis.engineering.network.physical_ports import physical_transmit_changes
    topology, hardware, interfaces = sample()
    topology, _ = materialize_physical_ports(topology, hardware, interfaces, [])
    for index, edge in enumerate(topology['edges']):
        edge['routingEntryIds'] = [f'route-{index}']
    routes = [{'id': f'route-{index}', 'approval_state': 'APPROVED', 'source': {'node_id': 'g'},
               'payload': {'message_id': 'm'}} for index in range(2)]
    message = {'id': 'm', 'interface_id': 'logical', 'hardware_interface_id': 'old-disconnected', 'configuration': {}}
    logical = {'id': 'logical', 'configuration': {'physical_interface_ids': ['old-disconnected'], 'endpoint_role': 'SYSTEM_CONTROLLER'}}
    before = deepcopy((topology, message, logical))
    changes = physical_transmit_changes(topology, routes, [message], logical_interfaces=[logical])
    update = next(c for c in changes if c['object_type'] == 'Interface')
    expected = sorted(p['hardwareInterfaceId'] for p in topology['nodes'][1]['ports'])
    assert update['data']['configuration'] == {'physical_interface_ids': expected, 'endpoint_role': 'SYSTEM_CONTROLLER'}
    assert physical_transmit_changes(topology, [{**r, 'approval_state': 'PENDING'} for r in routes],
                                     [message], logical_interfaces=[logical]) == []
    assert (topology, message, logical) == before
    applied_message = {**message, **next(c['data'] for c in changes if c['object_type'] == 'Message')}
    applied_logical = {**logical, **update['data']}
    assert physical_transmit_changes(topology, routes, [applied_message], logical_interfaces=[applied_logical]) == []
    pending = {**message, 'id': 'unreviewed-sibling'}
    sibling_changes = physical_transmit_changes(topology, routes, [message, pending], logical_interfaces=[logical])
    sibling_update = next(c for c in sibling_changes if c['object_type'] == 'Interface')
    assert sibling_update['data']['configuration']['physical_interface_ids'] == sorted([*expected, 'old-disconnected'])
    assert not any(c.get('object_id') == pending['id'] for c in sibling_changes)


def test_retired_physical_channel_cannot_be_reused_or_connected():
    topology, hardware, interfaces = sample()
    interfaces[0]['lifecycle_state'] = 'superseded'
    assert 'PHYSICAL_CHANNEL_RETIRED' in {f['code'] for f in topology_port_findings(topology, hardware, interfaces)}
    repaired, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    assert repaired['nodes'][0]['ports'][0]['hardwareInterfaceId'] != interfaces[0]['id']
    assert interfaces[0]['id'] not in {c.get('object_id') for c in changes}


def test_split_keeps_parallel_old_bus_instead_of_stealing_its_channel():
    topology, hardware, interfaces = sample()
    before, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    interfaces = effective(interfaces, changes)
    updated = deepcopy(before)
    source = updated['nodes'][0]['ports'][0]
    primary = source['hardwareInterfaceId']
    updated['nodes'][0]['ports'].append({**source, 'id': 'parallel-source', 'physicalNetworkId': 'parallel'})
    gateway = updated['nodes'][1]['ports'][0]
    updated['nodes'][1]['ports'].append({**gateway, 'id': 'parallel-gateway', 'physicalNetworkId': 'parallel'})
    updated['edges'].append({**updated['edges'][0], 'id': 'parallel-edge', 'sourcePort': 'parallel-source',
                             'targetPort': 'parallel-gateway', 'physicalNetworkId': 'parallel'})
    repaired, changes = materialize_physical_ports(updated, hardware, interfaces,
        [{'id': 'CAN1', 'technology': 'CAN_FD'}, {'id': 'CAN2', 'technology': 'CAN_FD'}], previous_topology=before)
    canonical = effective(interfaces, changes)
    assert next(p for p in canonical if p['id'] == primary)['network_ref'] == 'CAN1'
    assert repaired['nodes'][0]['ports'][1]['hardwareInterfaceId'] != primary
    assert not topology_port_findings(repaired, hardware, canonical)


def test_topology_refresh_reuses_reviewed_networks_ports_and_layout_without_wizard_prompt(monkeypatch):
    from backend.nis.agent.tools import wizard_generation as wizard_generation
    topology, hardware, interfaces = sample()
    topology, changes = materialize_physical_ports(topology, hardware, interfaces, [])
    interfaces = effective(interfaces, changes)
    topology['nodes'][0].update(x=1234, y=5678)
    hardware[0]['identity'] = {'system_owner_id': 'g'}
    routes = [{'id': 'route-' + str(index), 'source': {'node_id': left, 'protocol': 'CAN_FD', 'network_id': network},
        'destinations': [{'node_id': right, 'protocol': 'CAN_FD', 'network_id': network}],
        'route': {'hops': [{'node_id': left}, {'node_id': right}]}, 'approval_state': 'APPROVED', 'validation': {'valid': True}}
        for index, (left, right, network) in enumerate([('a', 'g', 'CAN1'), ('g', 'b', 'CAN2'), ('g', 'a', 'CAN1')])]
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda kind: hardware if kind == 'HardwareNode' else interfaces if kind == 'HardwareNetworkInterface' else [])
    monkeypatch.setattr(wizard_generation.model, 'routes', lambda: routes)
    monkeypatch.setattr(wizard_generation.model, 'networks', lambda: [{'id': net, 'technology': 'CAN_FD'} for net in ('CAN1', 'CAN2')])
    monkeypatch.setattr(wizard_generation, 'WorkflowStatusService', lambda _: type('Workflow', (), {'get': lambda _: {'topology': topology}})())
    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda **_: [])
    monkeypatch.setattr(wizard_generation.proposal_service, 'create', lambda kind, changes, *_, **__: {'changes': changes})
    result = wizard_generation.generate_network_topology({'prompt': 'Bestätigte Topologie um Rückmeldungen ergänzen.'})
    assert [change['object_type'] for change in result['changes']] == ['NetworkTopology']
    refreshed = result['changes'][0]['data']['topology']
    assert {edge['id'] for edge in refreshed['edges']} == {'e1', 'e2'}
    assert {edge['physicalNetworkId'] for edge in refreshed['edges']} == {'CAN1', 'CAN2'}
    node = next(node for node in refreshed['nodes'] if node['engineeringId'] == 'a')
    assert (node['id'], node['x'], node['y'], node['systemOwnerId']) == ('a', 1234, 5678, 'g')
    assert next(edge for edge in refreshed['edges'] if edge['id'] == 'e1')['routingEntryIds'] == ['route-0', 'route-2']


def test_network_topology_connects_gateway_with_confirmed_bus_without_gateway_message(monkeypatch):
    from backend.nis.agent.tools import wizard_generation as wizard_generation

    hardware = [
        {'id': 'controller', 'name': 'Controller', 'device_type': 'ECU'},
        {'id': 'sensor', 'name': 'Sensor', 'device_type': 'SensorController'},
        {'id': 'gateway', 'name': 'Gateway', 'device_type': 'Gateway'},
    ]
    interfaces = [
        {'id': f'{node}-can', 'name': f'{node} CAN', 'hardware_node_id': node,
         'technology': 'CAN_FD', 'network_ref': 'confirmed-can', 'channel_index': 1}
        for node in ('controller', 'sensor', 'gateway')
    ]
    routes = [{
        'id': 'sensor-to-controller', 'approval_state': 'APPROVED', 'validation': {'valid': True},
        'source': {'node_id': 'sensor', 'protocol': 'CAN_FD', 'network_id': 'confirmed-can'},
        'destinations': [{'node_id': 'controller', 'protocol': 'CAN_FD', 'network_id': 'confirmed-can'}],
        'route': {'hops': [{'node_id': 'sensor'}, {'node_id': 'controller'}]},
    }]
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda kind: hardware if kind == 'HardwareNode'
                        else interfaces if kind == 'HardwareNetworkInterface' else [])
    monkeypatch.setattr(wizard_generation.model, 'routes', lambda: routes)
    monkeypatch.setattr(wizard_generation.model, 'networks', lambda: [{'id': 'confirmed-can', 'name': 'Confirmed CAN', 'technology': 'CAN_FD'}])
    monkeypatch.setattr(wizard_generation, 'WorkflowStatusService', lambda _: type('Workflow', (), {'get': lambda _: {'topology': {}}})())
    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda **_: [])
    monkeypatch.setattr(wizard_generation.proposal_service, 'create', lambda kind, changes, *_, **__: {'changes': changes})

    result = wizard_generation.generate_network_topology({'prompt': 'Bestätigte CAN-Topologie.'})
    topology = next(change['data']['topology'] for change in result['changes']
                    if change['object_type'] == 'NetworkTopology')
    gateway = next(node for node in topology['nodes'] if node['engineeringId'] == 'gateway')
    assert any(port.get('hardwareInterfaceId') == 'gateway-can' for port in gateway['ports'])
    assert any(gateway['id'] in (edge['source'], edge['target']) for edge in topology['edges'])


def test_physical_channel_proposal_validates_applies_and_reloads_with_persisted_ids():
    from backend.nis.agent.api.tool_contract import Permission
    from backend.nis.agent.tools import model as model
    from backend.nis.agent.tools import proposal_service as proposal_service
    from backend.nis.agent.tools.runtime import ToolAuthority
    from backend.nis.agent.tools.runtime import execute
    from backend.nis.infrastructure.persistence.repository import create_object
    from backend.nis.workflow.services.service import WorkflowStatusService
    authority = ToolAuthority('physical-ports-' + uuid4().hex, 'test-human')

    def scoped(operation):
        result = execute(authority, 'physical-port-regression', Permission.READ_MODEL, {}, lambda _: operation())
        assert result.success, result
        return result.data

    def prepare():
        old, hardware, interfaces = sample()
        ids = {}
        for row in hardware:
            obj = create_object('HardwareNode', {'name': row['name'], 'device_type': row['device_type']})
            ids[row['id']] = str(obj['id'])
            row['id'] = str(obj['id'])
        for node in old['nodes']:
            node['engineeringId'] = ids[node['engineeringId']]
        for row in interfaces:
            row['hardware_node_id'] = ids[row['hardware_node_id']]
            obj = create_object('HardwareNetworkInterface', {key: value for key, value in row.items() if key != 'id'})
            ids[row['id']] = str(obj['id'])
            row['id'] = str(obj['id'])
        for node in old['nodes']:
            for port in node['ports']:
                port['hardwareInterfaceId'] = ids[port['hardwareInterfaceId']]
                port['engineeringId'] = port['hardwareInterfaceId']
        topology, changes = materialize_physical_ports(old, hardware, interfaces, [])
        # No model effects before explicit approval/apply.
        proposal = proposal_service.create('PHYSICAL_CHANNEL_REPAIR', [*changes, {'object_type': 'NetworkTopology', 'data': {'name': 'Reviewed channels', 'topology': topology}}], 'Hardwarekanäle korrigieren')
        return proposal_service.validate(proposal['proposal_id'])

    proposal = scoped(prepare)
    assert proposal['status'] == 'VALIDATED', proposal['validation_result']
    assert len(scoped(lambda: model.objects('HardwareNetworkInterface'))) == 3
    reviewed = scoped(lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='test-human', trace_id=uuid4().hex))
    assert reviewed['status'] == 'APPROVED'
    applied = scoped(lambda: proposal_service.apply(proposal['proposal_id'], actor='test-human', trace_id=uuid4().hex))
    assert applied['status'] == 'APPLIED'
    def reload():
        state = WorkflowStatusService(authority.project_id).get()
        assert state['statuses']['network_editor'] == 'COMPLETE'
        assert state['artifact_checks']['network_editor']['complete']
        assert not topology_port_findings(state['topology'], model.objects('HardwareNode'), model.objects('HardwareNetworkInterface'))
        assert all(not port['hardwareInterfaceId'].startswith('$') for node in state['topology']['nodes'] for port in node['ports'])
        return materialize_physical_ports(state['topology'], model.objects('HardwareNode'), model.objects('HardwareNetworkInterface'), model.networks())[1]
    assert scoped(reload) == []
