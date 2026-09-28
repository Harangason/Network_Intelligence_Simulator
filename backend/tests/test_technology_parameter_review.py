from copy import deepcopy
import pytest
from backend.engineering.capacity.service import parameters_for_protocol
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.project_context import current_project_id


def reviewed(values):
    return {'values': values, 'provenance': {key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value} for key, value in values.items()}}


def mixed():
    return {'industry': 'automotive', 'technology': 'can_fd', 'bitrate': 2_000_000, 'arbitration_bitrate': 500_000, 'data_bitrate': 2_000_000,
            'defaults_source': 'technology-registry', 'cycle_ms': 100, 'payload_bytes': 8, 'queue_size': 256,
            'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90, 'formats': ['universal-jsonl'],
            'networks': [{'id': 'lin-1', 'technology': 'LIN'}, {'id': 'can-1', 'technology': 'CAN_FD'}],
            'technology_defaults': {'lin': {'bitrate': 19200}}}


def test_profile_proposal_is_not_confirmed_capacity_evidence():
    p = mixed()
    result = parameters_for_protocol('LIN', p, network_id='lin-1', confirmed_parameters=p)
    assert not result['_rate_evidenced']
    assert 'bitrate' not in result


def test_confirmed_lin_group_does_not_change_can_fd_or_ethernet():
    p = mixed(); p['technology_parameters'] = {'lin': reviewed({'bitrate': 19200, 'cycle_ms': 50})}
    lin = parameters_for_protocol('LIN', p, network_id='lin-1', confirmed_parameters=p)
    assert lin['bitrate'] == 19200 and lin['cycle_ms'] == 50 and lin['_rate_evidenced']
    assert parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)['bitrate'] == 2_000_000
    assert 'bitrate' not in parameters_for_protocol('ETHERNET', p, confirmed_parameters=p)


def test_modified_or_proposed_group_cannot_reuse_old_confirmation():
    p = mixed(); p['technology_parameters'] = {'lin': reviewed({'bitrate': 19200})}
    p['technology_parameters']['lin']['values']['bitrate'] = 9600
    assert not parameters_for_protocol('LIN', p, confirmed_parameters=p)['_rate_evidenced']
    p['technology_parameters']['lin']['provenance']['bitrate']['value'] = 9600
    p['technology_parameters']['lin']['provenance']['bitrate']['status'] = 'REVIEW_REQUIRED'
    assert not parameters_for_protocol('LIN', p, confirmed_parameters=p)['_rate_evidenced']


def test_explicit_network_rate_overrides_the_confirmed_group():
    p = mixed(); p['technology_parameters'] = {'lin': reviewed({'bitrate': 19200})}; p['networks'][0]['bitrate'] = 9600
    assert parameters_for_protocol('LIN', p, network_id='lin-1', confirmed_parameters=p)['bitrate'] == 9600


@pytest.mark.parametrize('values', [{'bitrate': 2_000_000}, {'bitrate': 19200, 'data_bitrate': 2_000_000}, {'bitrate': float('nan')}, {'bitrate': True}])
def test_invalid_or_foreign_lin_group_rejected(values):
    p = mixed(); p['technology_parameters'] = {'lin': reviewed(values)}
    with pytest.raises(ValueError): WorkflowStatusService._validate_parameter_reviews(p, mixed())


def test_valid_group_roundtrip_preserves_inventory_and_invalidates_dependents():
    service = WorkflowStatusService(current_project_id()); base = mixed(); service.save_parameters(base)
    service.mark_changed('capacity_timing', 'Testberechnung vorhanden', status='COMPLETE')
    changed = deepcopy(base); changed['technology_parameters'] = {'lin': reviewed({'bitrate': 19200})}
    saved = service.save_parameters(changed)
    assert saved['parameters']['networks'] == base['networks']
    assert saved['parameters']['technology'] == 'can_fd'
    assert service.get()['parameters']['technology_parameters']['lin']['values']['bitrate'] == 19200
    assert saved['statuses']['capacity_timing'] == 'OUTDATED'


def test_unconfirmed_group_cannot_be_saved_as_confirmed():
    p = mixed(); p['technology_parameters'] = {'lin': {'values': {'bitrate': 19200}, 'provenance': {}}}
    with pytest.raises(ValueError, match='bestätigt'): WorkflowStatusService._validate_parameter_reviews(p, mixed())


def test_invalid_network_edit_rejected_without_mutation():
    service = WorkflowStatusService(current_project_id()); base = mixed(); service.save_parameters(base)
    changed = deepcopy(base); changed['networks'][0]['bitrate'] = 2_000_000
    with pytest.raises(ValueError): service.save_parameters(changed)
    assert service.get()['parameters'] == base


def test_valid_can_fd_group_keeps_separate_phases():
    p = mixed(); p['technology_parameters'] = {'can_fd': reviewed({'bitrate': 2_000_000, 'arbitration_bitrate': 500_000, 'data_bitrate': 2_000_000})}
    WorkflowStatusService._validate_parameter_reviews(p, mixed())
    result = parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)
    assert result['_rate_evidenced'] and result['arbitration_bitrate'] == 500_000 and result['data_bitrate'] == 2_000_000
