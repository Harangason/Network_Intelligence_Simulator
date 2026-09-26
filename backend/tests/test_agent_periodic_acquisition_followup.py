"""Real persisted context extension; no completion or transport mocks."""
import asyncio
import json
from copy import deepcopy
from uuid import uuid4
import pytest

from backend.tests.test_agent_periodic_acquisition_complete import seed, invoke
from backend.tests.test_agent_recipient_repair_runtime import scoped
from backend.engineering.agent_tools import conversation, model, proposal_service
from backend.engineering.repository import create_object, update_object
from backend.engineering.goal_execution.store import resources, save_resource
from backend.engineering.workflow.service import WorkflowStatusService

FOLLOWUP = 'Mach das auch für die anderen Aktoren.'


def apply(authority, result):
    proposal = result['proposals'][0]
    def run():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        saved = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        conversation.reconcile_runtime_model_apply(saved)
        return conversation.read()['engineering_workloads'][result['runtime']['workload_id']]
    return scoped(authority, run)


def add_actuator(authority, ids):
    def run():
        current = model.model(); mapping = {}
        def remap(v):
            if isinstance(v, dict): return {k: remap(x) for k, x in v.items()}
            if isinstance(v, list): return [remap(x) for x in v]
            return mapping.get(v, v) if isinstance(v, str) else v
        def clone(kind, row, keys):
            saved = create_object(kind, {**remap({k: row[k] for k in keys if k in row}), 'name': 'Additional_' + row['name']})
            mapping[str(row['id'])] = str(saved['id']); return saved
        original = next(x for x in current['hardware'] if x['id'] == ids['actuator'])
        node = clone('HardwareNode', original, ['device_type', 'device_class'])
        fn = next(x for x in current['functions'] if x['hardware_node_id'] == ids['actuator'])
        clone('Function', fn, ['hardware_node_id', 'configuration'])
        logical = next(x for x in current['interfaces'] if x['function_id'] == fn['id'])
        clone('Interface', logical, ['function_id', 'interface_type'])
        port = next(x for x in current['hardware-interfaces'] if x['hardware_node_id'] == ids['actuator'])
        for key in ('controller_ref', 'physical_port_ref'): mapping[port[key]] = str(uuid4())
        for kind, rows in resources().items():
            for row in rows:
                if row.get('hardware_node_ref') == ids['actuator'] or row.get('port_ref') == port['physical_port_ref']:
                    key = 'id' if 'id' in row else 'connection_id'
                    mapping.setdefault(row[key], str(uuid4())); save_resource(kind, remap(row))
        hni = clone('HardwareNetworkInterface', port, ['hardware_node_id', 'technology', 'controller_ref', 'channel_index', 'physical_port_ref', 'network_ref', 'bitrate', 'data_bitrate'])
        # PhysicalPort must point at the newly persisted HNI.
        resource = next(x for x in resources()['PhysicalPort'] if x['id'] == mapping[port['physical_port_ref']])
        save_resource('PhysicalPort', {**resource, 'hardware_interface_ref': str(hni['id'])})
        resource = next(x for x in resources()['NetworkConnection'] if x['port_ref'] == mapping[port['physical_port_ref']])
        save_resource('NetworkConnection', {**resource, 'technology_binding_ref': str(hni['id'])})
        message = deepcopy(next(x for x in current['messages'] if x['id'] == ids['position_message']))
        message['message_id_hex'] = '0x103'
        message['configuration']['request_response_acquisition'].update(request_frame_id='0x203', response_frame_id='0x204')
        newmsg = clone('Message', message, ['interface_id', 'hardware_interface_id', 'cycle_ms', 'dlc', 'direction', 'message_id_hex', 'configuration'])
        for signal in current['signals']:
            if signal['message_id'] == message['id']:
                clone('Signal', signal, ['message_id', 'start_bit', 'length_bits', 'byte_order', 'data_type', 'factor', 'offset_value', 'min_value', 'max_value', 'unit', 'semantic', 'data', 'configuration'])
        workflow = WorkflowStatusService(authority.project_id); topology = deepcopy(workflow.get()['topology'])
        topology['nodes'].append({'id': 'additional', 'engineeringId': str(node['id']), 'name': node['name'], 'kind': 'ecu',
            'ports': [{'id': 'additional-port', 'hardwareInterfaceId': str(hni['id']), 'bus': 'CAN_FD', 'physicalNetworkId': 'acquisition-can'}]})
        edge = {'id': 'additional-wire', 'source': 'additional', 'target': 'node-1', 'sourcePort': 'additional-port', 'targetPort': 'drawing-1',
                'bus': 'CAN_FD', 'physicalNetworkId': 'acquisition-can', 'engineeringSegmentId': 'additional-wire', 'origin': 'CANONICAL_BUS_BINDING'}
        topology['edges'].append(edge); workflow.save_topology(topology, actor='SCRIPTED_TEST_FIXTURE')
        from backend.engineering.communication_repair import load_plan
        from backend.engineering.communication_contract_repair import scan_signal_recipients
        from backend.engineering.routing.validation import RoutingValidator
        from backend.engineering.routing.repository import create_route, save_validation, approve_routes
        planner, _ = load_plan()
        changes = [c for c in scan_signal_recipients(planner, RoutingValidator().validate)['changes'] if str(newmsg['id']) in c['data']['payload']['message_ids']]
        assert len(changes) == 1
        route = create_route({**changes[0]['data'], 'origin': 'MANUAL'})
        validation = RoutingValidator().validate(route, exclude_route_id=str(route['id'])); assert validation['valid']
        save_validation(str(route['id']), validation); approve_routes([str(route['id'])])
        edge['routingEntryIds'] = [str(route['id'])]; workflow.save_topology(topology, actor='SCRIPTED_TEST_FIXTURE')
        return {'actuator': str(node['id']), 'position': mapping[ids['position']]}
    return scoped(authority, run)


def followup(authority, prompt=FOLLOWUP):
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.runtime.service import EngineeringAssistantService
    from backend.simulator_engineering_mcp.server import create_server
    started = scoped(authority, lambda: conversation.begin(prompt, AgentContext(active_project_id=authority.project_id)))
    run_id = started['run_id']
    class NoReasoner:
        async def next(self, *args): raise AssertionError('Canonical continuation must not fall through to general planning.')
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=NoReasoner(),
                persist=lambda w: scoped(authority, lambda: conversation.save_runtime_workload(run_id, w))).execute(
                    prompt, AgentContext.model_validate(started['context']), saved_state=scoped(authority, conversation.read),
                    emit=lambda e: scoped(authority, lambda: conversation.record_event(run_id, e)) if e.get('id') else None)
    result = asyncio.run(run()); scoped(authority, lambda: conversation.finish(run_id)); return result


def setup():
    authority, ids = seed(); original = invoke(authority); work = apply(authority, original)
    assert work['status'] == 'COMPLETED'; added = add_actuator(authority, ids)
    return authority, ids, work, added


def test_original_followup_reuses_acquisition_and_only_adds_remaining_actor():
    authority, ids, prior, added = setup(); before = scoped(authority, model.model)
    result = followup(authority)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', json.dumps(result['events'], ensure_ascii=True)
    proposal = result['proposals'][0]
    assert scoped(authority, model.model) == before
    assert len(proposal['changes']) == 7
    assert [c['object_type'] for c in proposal['changes']].count('RoutingEntry') == 2
    assert [c['object_type'] for c in proposal['changes']].count('Message') == 2
    work = apply(authority, result); after = scoped(authority, model.model)
    assert work['status'] == 'COMPLETED', work
    assert work['goal']['follow_up_of'] == prior['workload_id']
    acquisition = work['result']['periodic_acquisition']; previous = prior['result']['periodic_acquisition']
    assert acquisition['requester_id'] == previous['requester_id']
    assert acquisition['function_id'] == previous['function_id']
    assert acquisition['period_ms'] == 30000
    assert acquisition['actuator_ids'] == [ids['actuator'], added['actuator']]
    assert acquisition['source_signal_ids'] == [ids['position'], added['position']]
    for key in ('hardware', 'interfaces', 'hardware-interfaces', 'messages', 'signals', 'communication_resources'):
        if key == 'communication_resources': assert after[key] == before[key]
        else: assert all(row == next(x for x in after[key] if x['id'] == row['id']) for row in before[key]), key
    from backend.engineering.simulation import prepare_workflow_simulation_config
    from hardware_profile import normalize_hardware_config
    from universal_trace import generate_universal_events
    config = scoped(authority, lambda: prepare_workflow_simulation_config(
        {'duration_s': 61, 'max_events': 25000, 'seed': 42, 'scenario': {'mode': 'NORMAL'}}, authority.project_id))
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    responses = [m for m in after['messages'] if m['configuration'].get('generation_role') == 'ACQUISITION_RESPONSE']
    assert len(responses) == 2
    for response in responses:
        replies = [e for e in events if response['id'] in e.get('message_ids', [])]
        assert len(replies) >= 2
        for reply in replies:
            request = next(e for e in events if e['event_id'] == reply['caused_by_event_id'])
            assert request['transaction_id'] == reply['transaction_id']
            assert reply['scheduled_time_s'] >= request['time_s'] + .001 - 1e-9
    again = followup(authority)
    assert not again['proposals']
    assert scoped(authority, model.model) == after
    assert again['runtime']['workload_id'] != work['workload_id']
    assert scoped(authority, conversation.read)['engineering_workloads'][work['workload_id']]['status'] == 'COMPLETED'
    assert any(f.get('code') == 'ACQUISITION_ALREADY_COVERED' for e in again['events'] for f in e.get('findings', []))


@pytest.mark.parametrize('change', ['period', 'source', 'request', 'status', 'foreign', 'encoding', 'unconfirmed'])
def test_changed_or_invalid_prior_acquisition_blocks_without_model_writes(change):
    authority, ids, prior, added = setup()
    def alter():
        if change in {'status', 'foreign'}:
            state = conversation.read(); work = state['engineering_workloads'][prior['workload_id']]
            work['status' if change == 'status' else 'project_id'] = 'BLOCKED' if change == 'status' else 'different-project'
            conversation.write(state)
        elif change in {'period', 'source'}:
            fn = next(f for f in model.objects('Function') if str(f['id']) == prior['result']['periodic_acquisition']['function_id'])
            cfg = deepcopy(fn['configuration']); cfg['cycle_time_ms' if change == 'period' else 'source_signal_refs'] = 123 if change == 'period' else []
            update_object('Function', str(fn['id']), {'configuration': cfg})
        elif change == 'encoding':
            update_object('Signal', ids['position'], {'factor': 0.2})
        elif change == 'unconfirmed':
            message = next(m for m in model.objects('Message') if str(m['id']) == ids['position_message'])
            config = deepcopy(message['configuration']); config['request_response_acquisition']['confirmed'] = False
            update_object('Message', ids['position_message'], {'configuration': config})
        else:
            msg = next(m for m in model.objects('Message') if m['configuration'].get('generation_role') == 'ACQUISITION_REQUEST')
            update_object('Message', str(msg['id']), {'cycle_ms': 500})
    scoped(authority, alter); before = scoped(authority, model.model)
    result = followup(authority)
    assert not result['proposals']; assert result['runtime']['status'] != 'COMPLETED'
    assert scoped(authority, model.model) == before


@pytest.mark.parametrize('prompt', ['Mach das auch für die anderen Aktoren und lösche die alte ECU.',
                                  'Mach das nicht auch für die anderen Aktoren.'])
def test_canonical_planner_rejects_mixed_or_negative_extension_intent(prompt):
    from backend.engineering.agent_tools.periodic_acquisition import prepare
    authority, _, _, _ = setup(); planned = followup(authority); before = scoped(authority, model.model)
    def check():
        state = conversation.read(); work = state['engineering_workloads'][planned['runtime']['workload_id']]
        work['goal']['original_request'] = prompt; conversation.write(state)
        result = prepare({'workload_id': work['workload_id']})
        assert result['supported'] and result['proposal'] is None
        assert result['findings'][0]['code'] == 'ACQUISITION_CONTINUATION_AMBIGUOUS'
    scoped(authority, check); assert scoped(authority, model.model) == before


@pytest.mark.parametrize('mutation', ['period', 'unrelated_field', 'duplicate', 'foreign_source', 'wrong_owner', 'delete'])
def test_preview_rejects_changes_outside_append_only_source_pairs(mutation):
    from backend.engineering.agent_tools.periodic_acquisition import proposed_model
    from backend.engineering.models import EngineeringValidationError
    authority, _, prior, _ = setup(); result = followup(authority)
    assert result['proposals'][0]['status'] == 'VALIDATED'
    changes = deepcopy(result['proposals'][0]['changes'])
    update = next(c for c in changes if c['action'] == 'UPDATE'); config = update['data']['configuration']
    if mutation == 'period': config['cycle_time_ms'] = 500
    elif mutation == 'unrelated_field': update['data']['name'] = 'Replaced'
    elif mutation == 'duplicate': config['actuator_refs'][-1] = config['actuator_refs'][0]
    elif mutation == 'foreign_source': config['source_signal_refs'][-1] = str(uuid4())
    elif mutation == 'wrong_owner': config['actuator_refs'][-1] = prior['result']['periodic_acquisition']['requester_id']
    else: update['action'] = 'DELETE'
    before = scoped(authority, model.model)
    def validate():
        with pytest.raises(EngineeringValidationError): proposed_model(changes)
    scoped(authority, validate); assert scoped(authority, model.model) == before


def test_concurrent_function_change_revokes_reviewed_extension():
    authority, _, prior, _ = setup(); result = followup(authority); proposal = result['proposals'][0]
    def stale():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        update_object('Function', prior['result']['periodic_acquisition']['function_id'], {'description': 'Concurrent human edit'})
    scoped(authority, stale); before = scoped(authority, model.model)
    def refused():
        result = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert result['status'] == 'OUTDATED'
        assert not result.get('canonical_ids')
    scoped(authority, refused); assert scoped(authority, model.model) == before
