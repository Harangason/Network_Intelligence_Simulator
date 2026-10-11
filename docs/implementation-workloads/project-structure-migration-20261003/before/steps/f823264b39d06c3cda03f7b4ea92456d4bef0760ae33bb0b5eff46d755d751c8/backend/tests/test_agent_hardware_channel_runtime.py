"""Real MCP, SQL proposal and canonical port evidence for hardware extension."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.goal_resolver import GoalResolver, GoalType
from backend.agent_core.runtime.hardware_intent import hardware_channel_intent
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools import conversation, model, proposal_service, hardware_channel
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import create_object, update_object
from backend.engineering.goal_execution.graph import ModelGraphService
from backend.engineering.goal_execution.store import resources
from backend.simulator_engineering_mcp.server import create_server

PROMPT = 'Füge dem Controller einen zweiten CAN-FD-Kanal hinzu.'


def scoped(authority, operation):
    result = execute(authority, 'hardware_channel_acceptance', Permission.GENERATE_PROPOSAL, {}, lambda _: operation())
    assert result.success, result.findings
    return result.data


def seed(maximum=2):
    authority = ToolAuthority('channel-' + uuid4().hex)

    def create():
        node = create_object('HardwareNode', {'name': 'Controller', 'device_type': 'ECU'})
        capability = {'id': 'cap', 'hardware_node_ref': str(node['id']), 'technology': 'CAN_FD',
                      'supported': True, 'controller_count': 1, 'max_channels': maximum, 'max_ports': maximum}
        controller = {'id': 'controller-can', 'hardware_node_ref': str(node['id']), 'technology': 'CAN_FD',
                      'max_channels': maximum, 'active_channels': [1], 'status': 'ACTIVE'}
        node = update_object('HardwareNode', str(node['id']), {'hardware_information': {
            **node['hardware_information'], 'communication_capabilities': [capability], 'communication_controllers': [controller]}})
        old = create_object('HardwareNetworkInterface', {'name': 'CAN-FD 1', 'hardware_node_id': str(node['id']),
            'technology': 'CAN_FD', 'controller_ref': controller['id'], 'channel_index': 1,
            'physical_port_ref': 'original-port', 'bitrate': 500000, 'data_bitrate': 2000000})
        return {'node': node, 'old': old}

    return authority, scoped(authority, create)


def invoke(authority):
    saved = []

    class NoReasoner:
        async def next(self, *args):
            raise AssertionError('Explicit channel requests must use current canonical resource inspection.')

    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=NoReasoner(),
                persist=lambda row: saved.append(deepcopy(row))).execute(PROMPT, AgentContext(active_project_id=authority.project_id))

    return asyncio.run(run()), saved


@pytest.mark.parametrize('technology', ['CAN-FD', 'CAN FD', 'LIN', 'UART'])
def test_channel_grammar_preserves_explicit_technology(technology):
    text = f'Füge dem Controller einen zweiten {technology}-Kanal hinzu.'
    intent = hardware_channel_intent(text)
    assert intent == {'hardware_reference': 'Controller', 'technology': technology, 'channel_index': 2}
    goal = GoalResolver().resolve(text)
    assert goal.goal_type == GoalType.EXTEND_HARDWARE
    assert goal.requested_changes


@pytest.mark.parametrize('text', [
    'Füge dem Controller keinen zweiten CAN-FD-Kanal hinzu.',
    'Füge dem Controller einen zweiten CAN-FD-Kanal nicht hinzu.',
    'Kannst du dem Controller einen zweiten CAN-FD-Kanal hinzufügen?',
    PROMPT + ' Lösche den ersten Kanal.',
    'Füge dem Controller einen zweiten CAN-FD-Kanal hinzu und starte die Simulation.',
])
def test_channel_parser_does_not_authorize_negated_or_mixed_request(text):
    assert hardware_channel_intent(text) is None
    assert GoalResolver().resolve(text).goal_type != GoalType.EXTEND_HARDWARE


def test_exhausted_channel_reports_actual_hardware_limit_without_mutation():
    authority, data = seed(1)
    before = scoped(authority, model.model)
    result, saved = invoke(authority)
    assert result['runtime']['goal']['goal_type'] == 'EXTEND_HARDWARE'
    assert result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    answer = next(e for e in result['events'] if e['type'] == 'RESULT')
    assert answer['findings'][0]['code'] == 'HARDWARE_INTERFACE_CAPACITY_EXCEEDED'
    assert answer['metadata']['details']['controller_capacity']['available_channels'] == []
    assert {'inspect_communication_capability', 'inspect_controller_capacity', 'find_free_channel'} <= {t['tool'] for t in result['trace']}
    assert not result['proposals']
    assert scoped(authority, model.model) == before


def test_available_channel_is_reviewed_persisted_and_assessed_without_inventing_transport():
    authority, data = seed()
    result, saved = invoke(authority)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    proposal = result['proposals'][0]
    assert len(scoped(authority, lambda: model.objects('HardwareNetworkInterface'))) == 1
    assert not proposal['changes'][0]['data'].get('network_ref')
    assert not proposal['changes'][0]['data'].get('bitrate')

    def review_apply():
        state = conversation.read()
        state.setdefault('engineering_workloads', {})[saved[-1]['workload_id']] = saved[-1]
        conversation.write(state)
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=str(uuid4()))
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4()))
        assert conversation.reconcile_runtime_model_apply(applied)
        return applied

    applied = scoped(authority, review_apply)
    interfaces = scoped(authority, lambda: model.objects('HardwareNetworkInterface'))
    assert len(interfaces) == 2
    assert next(i for i in interfaces if str(i['id']) == data['old']['id']) == data['old']
    new = next(i for i in interfaces if i['channel_index'] == 2)
    ports = scoped(authority, resources)['PhysicalPort']
    assert len(ports) == 1 and ports[0]['hardware_interface_ref'] == str(new['id'])
    assert ports[0]['id'] == new['physical_port_ref'] and ports[0]['connection_status'] == 'FREE'
    workload = scoped(authority, conversation.read)['engineering_workloads'][saved[-1]['workload_id']]
    assert workload['status'] == 'COMPLETED', workload
    dependent = workload['result']['dependent_results']
    assert dependent['capacity_snapshot_id'] and dependent['preflight_snapshot_id']
    assert dependent['preflight_status'] == 'BLOCKED' and dependent['preflight_ready_for_simulation'] is False
    assert scoped(authority, lambda: proposal_service.apply(applied['proposal_id'], actor='human-test', trace_id=str(uuid4())))['status'] == 'APPLIED'
    assert len(scoped(authority, lambda: model.objects('HardwareNetworkInterface'))) == 2


def test_changed_capacity_invalidates_reviewed_channel():
    authority, data = seed()
    result, _ = invoke(authority)
    proposal = result['proposals'][0]
    scoped(authority, lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=str(uuid4())))

    def reduce():
        info = deepcopy(data['node']['hardware_information'])
        info['communication_controllers'][0]['active_channels'] = [1, 2]
        return update_object('HardwareNode', data['node']['id'], {'hardware_information': info})

    scoped(authority, reduce)
    applied = scoped(authority, lambda: proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4())))
    assert applied['status'] == 'OUTDATED'
    assert len(scoped(authority, lambda: model.objects('HardwareNetworkInterface'))) == 1


@pytest.mark.parametrize('alter,code', [
    (lambda info: info['communication_controllers'][0].update(active_channels=[1, 2]), 'HARDWARE_INTERFACE_CAPACITY_EXCEEDED'),
    (lambda info: info['communication_capabilities'][0].pop('max_ports'), 'HARDWARE_CAPACITY_UNKNOWN'),
    (lambda info: info['communication_capabilities'][0].update(supported=False), 'COMMUNICATION_CAPABILITY_MISSING'),
])
def test_current_resource_gaps_are_explicit(alter, code):
    authority, data = seed()
    info = deepcopy(data['node']['hardware_information'])
    alter(info)
    scoped(authority, lambda: update_object('HardwareNode', data['node']['id'], {'hardware_information': info}))
    result = scoped(authority, lambda: hardware_channel.inspect_request({'request': PROMPT}))
    assert result['status'] == 'BLOCKED'
    assert result['findings'][0]['code'] == code


def test_unknown_or_application_technology_does_not_fall_back_to_can():
    authority, _ = seed()
    for technology in ['NotARealTechnology', 'CANopen']:
        result = scoped(authority, lambda: hardware_channel.inspect_request({'request': PROMPT.replace('CAN-FD', technology)}))
        assert result['status'] == 'BLOCKED'
        assert result['findings'][0]['code'] == 'HARDWARE_CHANNEL_TECHNOLOGY_UNSUPPORTED'


def test_multiple_eligible_controllers_require_explicit_selection():
    authority, data = seed()
    info = deepcopy(data['node']['hardware_information'])
    info['communication_capabilities'][0].update(controller_count=2, max_channels=4, max_ports=4)
    info['communication_controllers'].append({**info['communication_controllers'][0], 'id': 'second-controller', 'active_channels': []})
    scoped(authority, lambda: update_object('HardwareNode', data['node']['id'], {'hardware_information': info}))
    before = scoped(authority, model.model)
    result, _ = invoke(authority)
    assert result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    assert next(e for e in result['events'] if e['type'] == 'RESULT')['findings'][0]['code'] == 'HARDWARE_CONTROLLER_AMBIGUOUS'
    assert not result['proposals']
    assert scoped(authority, model.model) == before


def test_existing_requested_channel_cannot_be_duplicated():
    authority, data = seed()
    scoped(authority, lambda: create_object('HardwareNetworkInterface', {
        'name': 'Existing second channel', 'hardware_node_id': data['node']['id'],
        'technology': 'CAN_FD', 'controller_ref': 'controller-can', 'channel_index': 2,
        'physical_port_ref': 'already-present'}))
    before = scoped(authority, model.model)
    inspected = scoped(authority, lambda: hardware_channel.inspect_request({'request': PROMPT}))
    assert inspected['status'] == 'ALREADY_PRESENT'
    result, _ = invoke(authority)
    assert not result['proposals']
    assert scoped(authority, model.model) == before


def test_port_persistence_failure_rolls_back_interface_and_proposal(monkeypatch):
    authority, _ = seed()
    result, _ = invoke(authority)
    proposal = result['proposals'][0]
    scoped(authority, lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=str(uuid4())))
    before = scoped(authority, model.model)

    def fail(*args):
        raise ValueError('Injected physical-port persistence failure')

    monkeypatch.setattr(hardware_channel, 'persist_port', fail)
    attempt = execute(authority, 'hardware_channel_atomic_failure', Permission.GENERATE_PROPOSAL, {},
                      lambda _: proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4())))
    assert not attempt.success
    assert scoped(authority, model.model) == before
    assert not scoped(authority, resources).get('PhysicalPort')
    assert scoped(authority, lambda: proposal_service.get(proposal['proposal_id']))['status'] == 'APPROVED'
