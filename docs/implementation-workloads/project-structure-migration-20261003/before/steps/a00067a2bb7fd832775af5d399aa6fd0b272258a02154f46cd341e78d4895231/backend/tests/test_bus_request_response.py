"""Actual scheduled bus requests, never synthetic periodic responses."""
from copy import deepcopy

import pytest

from backend.engineering.capacity.transmission import bus_request_pairs, profile, release_grid
from backend.tests.test_model_based_simulation import simulation_config
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


CONTRACT = {'mode': 'ON_REQUEST', 'request_source': 'bus_message', 'request_message_ref': 'request',
            'minimum_interval_ms': 5, 'response_processing_ms': 1}


def traffic(tmp_path):
    config = simulation_config(tmp_path)
    config['communications'] = [
        {'id': 'request-route', 'sender_interface': 'if-ecu', 'receiver_interfaces': ['if-sensor'],
         'network': 'can-main', 'technology': 'can_fd', 'cycle_ms': 20, 'payload_bytes': 1,
         'message_ids': ['request'], 'arbitration_id': 0x100, 'transmission_contract': {'mode': 'CYCLIC', 'period_ms': 20}},
        {'id': 'response-route', 'sender_interface': 'if-sensor', 'receiver_interfaces': ['if-ecu'],
         'network': 'can-main', 'technology': 'can_fd', 'cycle_ms': 5, 'payload_bytes': 8,
         'message_ids': ['msg-1'], 'signal_ids': ['sig-temperature'], 'arbitration_id': 0x101,
         'transmission_contract': deepcopy(CONTRACT)}]
    return config


def run(config):
    return generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)[1]


def test_response_follows_delivered_request_and_reads_payload_at_response_time(tmp_path):
    config = traffic(tmp_path)
    events = run(config)
    requests = {event['event_id']: event for event in events if event['route_id'] == 'request-route'}
    responses = [event for event in events if event['route_id'] == 'response-route']
    assert len(responses) == 4
    for response in responses:
        request = requests[response['caused_by_event_id']]
        assert response['transaction_id'] == request['transaction_id']
        assert response['scheduled_time_s'] == pytest.approx(request['time_s'] + .001)
        assert response['tx_start_s'] >= response['scheduled_time_s']
        assert response['release_basis'] == 'delivered_bus_request'
        assert response['signals']
    assert len({row['payload_hex'] for row in responses}) > 1


@pytest.mark.parametrize('fault', ['dropout_probability', 'corruption_probability'])
def test_undelivered_request_never_produces_response(tmp_path, fault):
    config = traffic(tmp_path)
    config['communications'][0]['fault_model'] = {fault: 1}
    assert run(config)
    assert not any(row['route_id'] == 'response-route' for row in run(config))


def test_offline_requester_never_produces_response(tmp_path):
    config = traffic(tmp_path)
    config['hardware']['devices'][1]['health'] = 'offline'
    assert run(config) == []


@pytest.mark.parametrize('patch', [
    {'request_message_ref': 'missing'}, {'request_message_ref': 'msg-1'},
    {'response_processing_ms': None}, {'response_processing_ms': -1},
    {'response_processing_ms': float('nan')}, {'minimum_interval_ms': 25},
    {'request_times_ms': [0, 20]},
])
def test_invalid_response_contract_rejected_before_simulation(tmp_path, patch):
    config = traffic(tmp_path)
    config['communications'][1]['transmission_contract'].update(patch)
    with pytest.raises(ValueError):
        run(config)


def test_no_response_release_grid_without_actual_delivery():
    assert not profile(CONTRACT, 5)['errors']
    assert release_grid(CONTRACT, 5, 1000) == []


@pytest.mark.parametrize('patch', [
    {'consumers': ['third']}, {'producer': 'third'}, {'protocol': 'LIN'},
    {'network_id': 'different'}, {'route_segment_count': 2},
])
def test_cross_model_pair_validation_rejects_mismatched_endpoints(patch):
    request = {'message_id': 'request', 'producer': 'a', 'consumers': ['b'], 'protocol': 'CAN_FD',
               'network_id': 'bus', 'cycle_ms': 20, 'transmission_contract': {'mode': 'CYCLIC'}}
    response = {**request, 'message_id': 'response', 'producer': 'b', 'consumers': ['a'],
                'cycle_ms': 5, 'transmission_contract': CONTRACT}
    assert bus_request_pairs([request, response]) == [(request, response)]
    with pytest.raises(ValueError):
        bus_request_pairs([request, {**response, **patch}])


@pytest.mark.parametrize('deadline,expected', [(30, 'PASS'), (20, 'FAIL'), (None, 'UNVERIFIED')])
def test_capacity_checks_complete_exchange_separately_from_frame_bounds(deadline, expected):
    from backend.engineering.capacity.dimensioning import bus_schedule, policy_for
    requirements = {'confirmed': True, 'maximum_event_to_response_ms': deadline,
                    'sampling_delay_ms': 0, 'actuation_delay_ms': 0}
    request = {'stream_id': 'request-stream', 'message_id': 'request', 'producer': 'a', 'consumers': ['b'],
        'network_id': 'bus', 'protocol': 'CAN_FD', 'cycle_ms': 20, 'payload_bytes': 1, 'bitrate': 500000,
        'segment_transmission_latency_ms': .1, 'frame_time_bound_ms': .2, 'arbitration_id': 0x100,
        'transmission_contract': {'mode': 'CYCLIC'}}
    response = {**request, 'stream_id': 'response-stream', 'message_id': 'response', 'producer': 'b',
        'consumers': ['a'], 'cycle_ms': 5, 'arbitration_id': 0x101,
        'transmission_contract': {**CONTRACT, 'functional_requirements': requirements}}
    result = bus_schedule([request, response], policy_for({'industry': 'industrial_automation'}))
    assert result['responses']['response-stream'] < 1
    exchange = result['request_exchanges'][0]
    assert exchange['request_to_response_bound_ms'] > 6
    assert exchange['event_to_response_bound_ms'] == pytest.approx(20 + exchange['request_to_response_bound_ms'])
    assert exchange['status'] == expected
    assert (result['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS') is (expected == 'PASS')
    response['transmission_contract']['request_message_ref'] = 'absent'
    assert bus_schedule([request, response], policy_for({}))['status'] == 'PROFILE_INCOMPLETE'
