"""Model-defined diagnostic reads reuse real governed acquisition and physics."""
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.tests.test_agent_periodic_acquisition_complete import seed
from backend.tests.test_agent_periodic_acquisition_followup import add_actuator, followup, apply
from backend.tests.test_agent_recipient_repair_runtime import scoped
from backend.nis.agent.tools import conversation as conversation
from backend.nis.agent.tools import model as model
from backend.nis.agent.tools import proposal_service as proposal_service
from backend.nis.infrastructure.persistence.repository import update_object

PROMPT = 'Lege eine Diagnoseabfrage für alle Stellglieder an.'


@pytest.mark.parametrize('recipient,valid', [('receiver', True), ('receiver-function', True),
    ('receiver-interface', True), ('foreign', False), ('producer-function', False),
    ('dangling-function-interface', False), ('contradictory-interface', False)])
def test_function_contract_recipient_must_resolve_to_actual_transport_owner(recipient, valid):
    from backend.nis.engineering.communication.wizard_communication import contract_findings
    graph = {'HardwareNode': {'producer': {}, 'receiver': {}},
        'Function': {'receiver-function': {'hardware_node_id': 'receiver'}, 'producer-function': {'hardware_node_id': 'producer'}},
        'Interface': {'receiver-interface': {'function_id': 'receiver-function', 'hardware_node_id': 'receiver'},
            'dangling-function-interface': {'function_id': 'missing', 'hardware_node_id': 'receiver'},
            'contradictory-interface': {'function_id': 'receiver-function', 'hardware_node_id': 'producer'}},
        'Message': {'message': {'name': 'Diagnostic', 'configuration': {
            'communication_contract': {'scope': 'FUNCTION_OUTPUT', 'consumer_refs': [recipient]},
            'transport_unit': {'consumer_refs': ['receiver'], 'producer_ref': 'producer'}}}}}
    assert (not contract_findings(graph)) is valid


def fixture():
    authority, ids = seed(); added = add_actuator(authority, ids)
    def define():
        fn = next(f for f in model.objects('Function') if f['hardware_node_id'] == ids['controller'])
        definition = {'confirmed': True, 'trigger': 'CYCLIC', 'period_ms': 30000,
            'service_id': 'read_actual_position', 'requester_hardware_interface_ref': ids['controller_port'],
            'source_signal_refs': [ids['position'], added['position']]}
        update_object('Function', fn['id'], {'configuration': {'diagnostic_request_template': definition}})
        return fn['id']
    ids.update(definition_function=scoped(authority, define), additional_position=added['position'])
    return authority, ids


def test_explicit_diagnostic_query_uses_existing_requester_and_real_exchange_assessment():
    authority, ids = fixture(); before = scoped(authority, model.model)
    result = followup(authority, PROMPT)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', '\n'.join(e.get('text', '') for e in result['events'])
    assert not any(e.get('question') for e in result['events'])
    assert scoped(authority, model.model) == before
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED'
    kinds = [c['object_type'] for c in proposal['changes']]
    assert len(kinds) == 14 and kinds.count('Function') == kinds.count('Interface') == 1
    assert kinds.count('Message') == kinds.count('Signal') == kinds.count('RoutingEntry') == 4
    assert all(c['action'] == 'CREATE' for c in proposal['changes'])
    work = apply(authority, result)
    assert work['status'] == 'COMPLETED', work['result']
    actual = work['result']['diagnostic_acquisition']
    assert actual['requester_id'] == ids['controller'] and actual['period_ms'] == 30000
    assert set(actual['source_signal_ids']) == {ids['position'], ids['additional_position']}
    after = scoped(authority, model.model)
    assert after['hardware'] == before['hardware']
    assert after['hardware-interfaces'] == before['hardware-interfaces']
    assert after['communication_resources'] == before['communication_resources']
    for section in ('functions', 'interfaces', 'messages', 'signals'):
        assert all(old == next(row for row in after[section] if row['id'] == old['id']) for old in before[section])
    query = next(f for f in after['functions'] if f['id'] == actual['function_id'])
    assert query['hardware_node_id'] == ids['controller']
    assert query['configuration']['diagnostic_service_id'] == 'read_actual_position'
    assert query['configuration']['diagnostic_definition_ref'] == ids['definition_function']
    from backend.nis.engineering.simulation import prepare_workflow_simulation_config
    from backend.nis.simulation.hardware_profile import normalize_hardware_config
    from backend.nis.traces.universal_trace import generate_universal_events
    config = scoped(authority, lambda: prepare_workflow_simulation_config(
        {'duration_s': 61, 'max_events': 20000, 'seed': 42, 'scenario': {'mode': 'NORMAL'}}, authority.project_id))
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    responses = [m for m in after['messages'] if m.get('configuration', {}).get('generation_role') == 'ACQUISITION_RESPONSE']
    assert len(responses) == 2
    for message in responses:
        request_id = message['configuration']['communication_contract']['transmission']['request_message_ref']
        requests = [e for e in events if request_id in e.get('message_ids', [])]
        replies = [e for e in events if message['id'] in e.get('message_ids', [])]
        assert len(requests) >= 2 and len(replies) >= 2
        assert requests[1]['origin_scheduled_time_s'] - requests[0]['origin_scheduled_time_s'] == 30
        for reply in replies:
            request = next(e for e in requests if e['event_id'] == reply['caused_by_event_id'])
            assert reply['transaction_id'] == request['transaction_id']
            assert reply['scheduled_time_s'] >= request['time_s'] + .001 - 1e-9
    again = followup(authority, PROMPT)
    assert not again['proposals'] and again['runtime']['workload_id'] != work['workload_id']
    assert scoped(authority, model.model) == after
    assert scoped(authority, conversation.read)['engineering_workloads'][work['workload_id']]['status'] == 'COMPLETED'


@pytest.mark.parametrize('field,value', [('confirmed', False), ('trigger', 'EVENT'), ('period_ms', 0),
    ('period_ms', True), ('service_id', ''), ('source_signal_refs', []),
    ('source_signal_refs', ['foreign-source']), ('requester_hardware_interface_ref', 'foreign-port')])
def test_unconfirmed_or_incomplete_definition_has_no_proposal_or_model_mutation(field, value):
    authority, ids = fixture()
    def alter():
        fn = next(f for f in model.objects('Function') if f['id'] == ids['definition_function'])
        config = deepcopy(fn['configuration']); config['diagnostic_request_template'][field] = value
        update_object('Function', fn['id'], {'configuration': config})
    scoped(authority, alter); before = scoped(authority, model.model)
    result = followup(authority, PROMPT)
    assert not result['proposals'] and result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    assert scoped(authority, model.model) == before


@pytest.mark.parametrize('change', ['missing_actuator', 'duplicate_source', 'unconfirmed_device', 'foreign_transport', 'frame_collision', 'ambiguous_template'])
def test_all_actuators_and_device_contracts_remain_mandatory(change):
    authority, ids = fixture()
    def alter():
        if change in {'missing_actuator', 'duplicate_source'}:
            fn = next(f for f in model.objects('Function') if f['id'] == ids['definition_function'])
            cfg = deepcopy(fn['configuration'])
            cfg['diagnostic_request_template']['source_signal_refs'] = [ids['position']] * (2 if change == 'duplicate_source' else 1)
            update_object('Function', fn['id'], {'configuration': cfg})
        elif change in {'unconfirmed_device', 'frame_collision'}:
            msg = next(m for m in model.objects('Message') if m['id'] == ids['position_message'])
            cfg = deepcopy(msg['configuration'])
            cfg['request_response_acquisition'].update({'confirmed': False} if change == 'unconfirmed_device' else {'request_frame_id': '0x100'})
            update_object('Message', msg['id'], {'configuration': cfg})
        elif change == 'ambiguous_template':
            fn = next(f for f in model.objects('Function') if f['id'] == ids['definition_function'])
            other = next(f for f in model.objects('Function') if f['id'] != ids['definition_function'])
            update_object('Function', other['id'], {'configuration': fn['configuration']})
        else:
            update_object('HardwareNetworkInterface', ids['controller_port'], {'technology': 'Ethernet'})
    scoped(authority, alter); before = scoped(authority, model.model)
    result = followup(authority, PROMPT)
    assert not result['proposals'] and result['runtime']['status'] != 'COMPLETED'
    assert scoped(authority, model.model) == before


def test_changed_diagnostic_definition_invalidates_reviewed_proposal():
    authority, ids = fixture(); result = followup(authority, PROMPT); proposal = result['proposals'][0]
    def change_and_apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        fn = next(f for f in model.objects('Function') if f['id'] == ids['definition_function'])
        cfg = deepcopy(fn['configuration']); cfg['diagnostic_request_template']['period_ms'] = 1000
        update_object('Function', fn['id'], {'configuration': cfg})
        before = model.model()
        saved = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert saved['status'] == 'OUTDATED' and model.model() == before
    scoped(authority, change_and_apply)


@pytest.mark.parametrize('prompt', ['Lege keine Diagnoseabfrage für alle Stellglieder an.',
    'Lege eine Diagnoseabfrage für alle Stellglieder an und lösche die vorhandene ECU.'])
def test_canonical_diagnostic_planner_does_not_consume_negated_or_mixed_intent(prompt):
    from backend.nis.agent.tools.periodic_acquisition import prepare_diagnostic
    authority, _ = fixture(); original = followup(authority, PROMPT); before = scoped(authority, model.model)
    def inspect():
        state = conversation.read(); work = state['engineering_workloads'][original['runtime']['workload_id']]
        work['goal']['original_request'] = prompt; conversation.write(state)
        return prepare_diagnostic({'workload_id': work['workload_id']})
    assert scoped(authority, inspect) == {'supported': False}
    assert scoped(authority, model.model) == before
