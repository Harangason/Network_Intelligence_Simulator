from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import proposal_service, wizard_generation
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.intelligence.network_planning import plan_network_distribution, split_topology_by_distribution
from backend.engineering.intelligence.resource_policy import planning_policy, resource_decision, planning_inventory
from backend.engineering.workflow.service import WorkflowStatusService
from backend.tests.test_network_distribution import capacity, hardware, topology


AUTO = {'mode': 'AUTO_SIZE', 'hard_limits': {}}


def test_automatic_sizing_adds_only_needed_same_technology_resources():
    source = capacity((40, 40))
    saved = deepcopy(source)
    plan = plan_network_distribution(source, hardware(), {}, available_protocol_counts={'LIN': 1, 'CAN_FD': 2}, resource_policy=AUTO)
    branch = plan['networks'][0]
    assert plan['status'] == 'PROPOSED'
    assert branch['decision'] == 'SPLIT_CURRENT_TECHNOLOGY'
    assert branch['selected_protocol'] == 'LIN'
    assert branch['new_resources_required'] == 1
    assert branch['resource_action'] == 'PLAN_ADDITIONAL_SEGMENTS'
    assert branch['projected_max_load_percent'] == 40
    stock = next(item for item in plan['resource_allocation'] if item['protocol'] == 'LIN')
    assert stock['recommended_count'] == 2 and stock['increase_over_baseline'] == 1
    assert source == saved


def test_free_segments_are_used_before_new_resources_are_planned():
    plan = plan_network_distribution(capacity((40, 40)), hardware(), {}, available_protocol_counts={'LIN': 2}, resource_policy=AUTO)
    assert plan['networks'][0]['new_resources_required'] == 0
    assert plan['networks'][0]['resource_action'] == 'USE_EXISTING_SEGMENTS'


def test_multiple_branches_do_not_double_spend_existing_inventory():
    source = capacity((40, 40))
    other = deepcopy(source['results']['routes'])
    for row in other:
        row.update(route_id='other-' + row['route_id'], network_id='other')
    source['results']['routes'].extend(other)
    plan = plan_network_distribution(source, hardware(), {}, available_protocol_counts={'LIN': 3}, resource_policy=AUTO)
    assert sorted(item['new_resources_required'] for item in plan['networks']) == [0, 1]
    assert plan['resource_allocation'][0]['recommended_count'] == 4
    assert plan['remaining_protocol_inventory']['LIN'] == 0


def test_initial_quantities_are_not_silently_treated_as_hard_limits_in_auto_mode():
    plan = plan_network_distribution(capacity((10, 10)), hardware(), {}, available_protocol_counts={'LIN': 0}, resource_policy=AUTO)
    assert plan['status'] == 'WITHIN_TARGET'
    assert plan['inventory_constraints'] == []
    assert plan['resource_allocation'][0]['increase_over_baseline'] == 1
    assert plan['resource_allocation'][0]['decision'] == 'KEEP_CURRENT_TOPOLOGY'


def test_explicit_hard_limits_still_block_automatic_expansion():
    plan = plan_network_distribution(capacity((40, 40)), hardware(), {}, available_protocol_counts={'LIN': 1},
        resource_policy={'mode': 'AUTO_SIZE', 'hard_limits': {'LIN': 1}})
    assert plan['status'] == 'RESIDUAL_CONSTRAINTS'
    assert plan['networks'][0]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'


def test_unsplittable_single_route_is_not_declared_fixed_by_more_segments():
    plan = plan_network_distribution(capacity((120, 20)), hardware(), {}, available_protocol_counts={'LIN': 1}, resource_policy=AUTO)
    assert plan['status'] == 'RESIDUAL_CONSTRAINTS'
    assert plan['networks'][0]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'


@pytest.mark.parametrize('raw', [{'mode': 'guess'}, {'hard_limits': {'lin': -1}}, {'hard_limits': {'lin': True}}, {'hard_limits': {'lin': 1.5}}])
def test_invalid_resource_policies_are_not_silently_accepted(raw):
    with pytest.raises(ValueError):
        planning_policy({'parameters': {'network_resource_policy': raw}})


def test_persisted_inventory_wins_over_a_continuation_prompt():
    state = {'context': {'agent_wizard_status': {'agent_prompt': '- Kommunikationssystem-Sollwerte: [{"id":"lin","count":1}]'}}}
    assert planning_inventory(state, '- Kommunikationssystem-Sollwerte: [{"id":"lin","count":999}]') == {'LIN': 1}


def test_auto_resource_receipt_is_revalidated_before_apply(monkeypatch):
    """Real proposal store/validate/review/apply, isolated project, no user changes."""
    authority = ToolAuthority('pytest-auto-resources-' + str(uuid4()))
    def work():
        from backend.engineering.repository import create_object
        from backend.engineering.agent_tools import model
        from backend.engineering.physical_ports import topology_port_findings
        workflow = WorkflowStatusService(authority.project_id)
        prompt = '- Kommunikationssystem-Sollwerte: [{"id":"lin","count":1}]'
        workflow.set_context({'agent_wizard_status': {'agent_prompt': prompt}})
        before = topology(shared=True)
        for node in before['nodes']:
            node.update(name=node['id'], kind='ecu')
            physical_node = create_object('HardwareNode', {'name': node['name'], 'device_type': 'ECU'})
            node['engineeringId'] = str(physical_node['id'])
            for index, port in enumerate(node['ports'], start=1):
                interface = create_object('HardwareNetworkInterface', {'name': f'LIN Kanal {index}',
                    'hardware_node_id': str(physical_node['id']), 'technology': 'LIN', 'channel_index': index,
                    'network_ref': 'network-lin'})
                port.update(engineeringId=str(interface['id']), hardwareInterfaceId=str(interface['id']), physicalNetworkId='network-lin')
        workflow.save_parameters({'networks': [{'id': 'network-lin', 'technology': 'LIN'}]})
        for index, edge in enumerate(before['edges']):
            edge.update(physicalNetworkId='network-lin', routingEntryId=f'r{index}',
                        routingEntryIds=[f'r{index}'], engineeringRelationId=f'relation-{index}')
        workflow.save_topology(before)
        plan = plan_network_distribution(capacity((40, 40)), hardware(), before, available_protocol_counts={'LIN': 1}, resource_policy=AUTO)
        after, count = split_topology_by_distribution(before, plan)
        assert count == 2
        monkeypatch.setattr(wizard_generation, 'plan_capacity_remediation', lambda arguments: deepcopy(plan))
        proposal = wizard_generation.generate_capacity_network_repair({'prompt': prompt})
        topology_change = next(change for change in proposal['changes'] if change['object_type'] == 'NetworkTopology')
        receipt = resource_decision(before, topology_change['data']['topology'], {'LIN': 1}, AUTO)
        assert topology_change['data']['resource_decision'] == receipt
        assert any(change['object_type'] == 'HardwareNetworkInterface' for change in proposal['changes'])
        assert 'Tool-Entscheidung:' in proposal['rationale']
        assert 'LIN 1 → 2' in proposal['rationale']
        validated = proposal_service.validate(proposal['proposal_id'])
        assert validated['status'] == 'VALIDATED', validated
        assert workflow.get()['topology'] == before, 'Planning must not apply changes.'
        approved = proposal_service.review(validated['proposal_id'], revision=validated['revision'], decision='approve', actor='test-human', trace_id=str(uuid4()))
        applied = proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        assert applied['status'] == 'APPLIED'
        persisted = workflow.get()['topology']
        assert {edge['physicalNetworkId'] for edge in persisted['edges']} == {edge['physicalNetworkId'] for edge in after['edges']}
        assert not topology_port_findings(persisted, model.objects('HardwareNode'), model.objects('HardwareNetworkInterface'))
        assert all(not port['hardwareInterfaceId'].startswith('$') for node in persisted['nodes'] for port in node['ports'])
        assert receipt['resources'][0]['planned_count'] == 2
        assert receipt['additional_modeled_ports']
    result = execute(authority, 'test_auto_resource_apply', Permission.GENERATE_PROPOSAL, {}, lambda _: work())
    assert result.success, result


def test_forged_stale_or_fixed_inventory_receipts_cannot_bypass_limits(monkeypatch):
    before = {'nodes': [], 'edges': [{'physicalNetworkId': 'n1', 'bus': 'lin'}]}
    after = {'nodes': [], 'edges': [*before['edges'], {'physicalNetworkId': 'n2', 'bus': 'lin'}]}
    state = {'topology': before, 'parameters': {}, 'context': {'agent_wizard_status': {
        'agent_prompt': '- Kommunikationssystem-Sollwerte: [{"id":"lin","count":1}]'}}}
    class Workflow:
        def __init__(self, *args): pass
        def get(self): return deepcopy(state)
    monkeypatch.setattr(proposal_service, 'WorkflowStatusService', Workflow)
    receipt = resource_decision(before, after, {'LIN': 1}, AUTO)
    changes = [{'object_type': 'NetworkTopology', 'data': {'topology': after, 'resource_decision': receipt}}]
    row = {'proposal_type': 'CAPACITY_NETWORK_REPAIR'}
    assert proposal_service._validate_topology_inventory(row, changes) == []
    receipt['resources'][0]['planned_count'] = 1
    assert any(item['code'] == 'RESOURCE_DECISION_OUTDATED' for item in proposal_service._validate_topology_inventory(row, changes))
    changes[0]['data']['resource_decision'] = resource_decision(before, after, {'LIN': 1}, AUTO)
    state['parameters']['network_resource_policy'] = {'mode': 'FIXED_INVENTORY'}
    assert any(item['code'] == 'PHYSICAL_INVENTORY_EXCEEDED' for item in proposal_service._validate_topology_inventory(row, changes))
    state['parameters']['network_resource_policy'] = {'mode': 'AUTO_SIZE', 'hard_limits': {'lin': 1}}
    assert any(item['code'] == 'PHYSICAL_HARD_LIMIT_EXCEEDED' for item in proposal_service._validate_topology_inventory(row, changes))
