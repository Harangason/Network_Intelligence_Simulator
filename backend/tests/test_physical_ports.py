"""Independent physical buses need real, reviewed and persistable channels."""
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.engineering.physical_ports import materialize_physical_ports, topology_port_findings


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
    from backend.engineering.intelligence.network_planning import split_topology_by_distribution
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


def test_malformed_topology_is_reported_instead_of_crashing_status_reads():
    assert {row['code'] for row in topology_port_findings({'nodes': [None], 'edges': ['broken']}, [], [])} == {
        'INVALID_TOPOLOGY_NODE', 'INVALID_TOPOLOGY_EDGE'}


def test_message_on_two_independent_channels_requires_explicit_transmit_bindings():
    from backend.engineering.physical_ports import physical_transmit_changes
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
    assert not physical_transmit_changes(topology, routes, [{**message, 'configuration': configuration}])


def test_topology_refresh_reuses_reviewed_networks_ports_and_layout_without_wizard_prompt(monkeypatch):
    from backend.engineering.agent_tools import wizard_generation
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


def test_physical_channel_proposal_validates_applies_and_reloads_with_persisted_ids():
    from backend.agent_core.api.tool_contract import Permission
    from backend.engineering.agent_tools import model, proposal_service
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService
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
