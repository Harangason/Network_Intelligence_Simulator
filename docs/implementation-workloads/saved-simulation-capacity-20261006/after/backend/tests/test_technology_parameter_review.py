from copy import deepcopy
import pytest


def test_capacity_parameter_validation_does_not_traverse_unrelated_project_graph():
    from backend.nis.engineering.capacity.service import parameters_for_protocol
    from backend.tests.native_transport_fixtures import lin_design

    class UnrelatedProjectGraph(dict):
        def __deepcopy__(self, memo):
            raise AssertionError('A native bus check must not copy the unrelated project graph.')

    values = lin_design()
    parameters = {'technology': 'lin', 'spatial_zoning': UnrelatedProjectGraph(nodes=[]),
        'technology_parameters': {'lin': {'values': values, 'provenance': {
            key: {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': value}
            for key, value in values.items()}}}}
    result = parameters_for_protocol('LIN', parameters, confirmed_parameters=parameters)
    assert result['_rate_evidenced'] is True
    assert result['spatial_zoning'] is parameters['spatial_zoning']
    # Undeclared native input still reaches the strict schema check.
    invalid = parameters_for_protocol('LIN', {**parameters, 'lin_unknown_native_field': 1},
                                      confirmed_parameters=parameters)
    assert invalid['_rate_evidenced'] is False
    assert any(row['code'] == 'TECHNOLOGY_PARAMETER_NOT_APPLICABLE' for row in invalid['_rate_findings'])


@pytest.mark.parametrize('technology,payload,bits,rate', [('lin',4,84,19200), ('can_fd',12,240,500000), ('ethernet',8,672,1000000000)])
def test_saved_simulation_values_reach_native_wire_model_without_hardware_confirmation(technology,payload,bits,rate):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
    service = WorkflowStatusService(current_project_id())
    base = {**mixed(), 'technology': 'can_fd'}
    saved = registry.simulation_defaults_for_project(base, [technology])
    service.save_parameters(saved)
    reloaded = service.get()['parameters']
    before = deepcopy(reloaded)
    resolved = simulation_parameters_for_protocol(technology, reloaded, confirmed_parameters=reloaded)
    assert resolved['_simulation_parameters_usable'], resolved['_simulation_parameter_findings']
    assert not resolved['_rate_evidenced']
    assert resolved['arbitration_bitrate' if technology == 'can_fd' else 'bitrate'] == rate
    frame = estimate_simulation_frame(technology, payload, resolved)
    assert frame.transmission_time_available and not frame.is_generic_estimate
    assert frame.frame_bits == bits
    expected = 80/500000 + 160/2000000 if technology == 'can_fd' else bits/rate
    assert frame.transmission_time_s == pytest.approx(expected)
    assert service.get()['parameters'] == before
    strict = parameters_for_protocol(technology, reloaded, confirmed_parameters=reloaded)
    assert not strict['_rate_evidenced']


@pytest.mark.parametrize('patch,proof_patch,code', [
    ({'lin_bitrate_bps':2000000},{},'TECHNOLOGY_PARAMETER_OUT_OF_RANGE'),
    ({'lin_node_count':200},{},'TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH'),
    ({},{'technology':'can_fd'},'SIMULATION_PARAMETER_PROVENANCE_MISMATCH'),
    ({},{'value':9600},'SIMULATION_PARAMETER_PROVENANCE_MISMATCH'),
])
def test_invalid_saved_simulation_context_is_not_repaired_by_a_foreign_clock_or_stale_proof(patch,proof_patch,code):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
    p = registry.simulation_defaults_for_project(mixed(), ['lin'])
    group = p['simulation_parameter_assumptions']['lin']
    for key,value in patch.items():
        group['values'][key]=value
        group['provenance'][key]['value']=value
    group['provenance']['lin_bitrate_bps'].update(proof_patch)
    before = deepcopy(p)
    resolved = simulation_parameters_for_protocol('lin',p,confirmed_parameters=p)
    assert not resolved['_simulation_parameters_usable']
    assert any(item['code'] == code for item in resolved['_simulation_parameter_findings'])
    assert not estimate_simulation_frame('LIN',2,resolved).transmission_time_available
    assert not resolved['_rate_evidenced'] and p == before


def test_explicit_lin_layout_is_not_overwritten_by_assumed_message_length():
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.nis.engineering.capacity.calculators import estimate_simulation_frame
    p=registry.simulation_defaults_for_project(mixed(),['lin'])
    p['technology_parameters']={'lin':reviewed({'lin_data_octets':1})}
    resolved=simulation_parameters_for_protocol('lin',p,confirmed_parameters=p)
    assert resolved['lin_data_octets']==1
    assert 'lin_data_octets' not in resolved['_simulation_assumption_fields']
    assert not estimate_simulation_frame('lin',4,resolved).transmission_time_available


def test_saved_interface_assumption_overrides_project_starter_without_becoming_hardware_evidence():
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    p=registry.simulation_defaults_for_project(mixed(),['lin'])
    group=deepcopy(p['simulation_parameter_assumptions']['lin'])
    group['values']['lin_bitrate_bps']=9600
    group['provenance']['lin_bitrate_bps']['value']=9600
    scoped={'technology':'lin','capabilities':{'simulation_parameter_assumptions':{'lin':group}}}
    resolved=simulation_parameters_for_protocol('lin',p,scoped,confirmed_parameters=p)
    assert resolved['bitrate']==9600 and resolved['_simulation_parameters_usable']
    assert not resolved['_rate_evidenced']


def test_complete_explicit_device_input_wins_over_obsolete_unused_assumptions():
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
    from backend.tests.native_transport_fixtures import lin_design
    p=registry.simulation_defaults_for_project(mixed(),['lin'])
    p['simulation_parameter_assumptions']['lin']['provenance']['lin_bitrate_bps']['value']=9600
    p['technology_parameters']={'lin':reviewed(lin_design())}
    resolved=simulation_parameters_for_protocol('lin',p,confirmed_parameters=p)
    assert resolved['_rate_evidenced'] and resolved['_simulation_parameters_usable']
    assert resolved['bitrate']==19200 and resolved['_simulation_assumption_fields']==[]


def test_capacity_service_exposes_saved_scenario_metrics_without_qualifying_device_or_timing(monkeypatch):
    from backend.nis.app import create_app
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.engineering.capacity.service import CapacityTimingService
    client = create_app(testing=True).test_client()
    client.environ_base['HTTP_X_PROJECT_ID'] = current_project_id()
    service = WorkflowStatusService(current_project_id())
    p = registry.simulation_defaults_for_project({'technology':'lin','industry':'automotive','defaults_source':'technology-registry',
        'networks':[{'id':'local-lin','technology':'LIN'}]},['lin'])
    service.save_parameters(p)
    def create(resource,data):
        response=client.post('/api/engineering/'+resource,json=data)
        assert response.status_code in {200,201},response.get_json()
        return response.get_json()
    node=create('hardware-nodes',{'name':'Scenario controller','device_type':'EmbeddedController'})
    port=create('hardware-interfaces',{'name':'Local LIN','hardware_node_id':node['id'],'technology':'LIN','network_ref':'local-lin','bitrate':None})
    logical=create('interfaces',{'name':'LIN producer','hardware_node_id':node['id'],'interface_type':'LIN'})
    message=create('messages',{'name':'Four byte command','interface_id':logical['id'],'hardware_interface_id':port['id'],'dlc':4,'cycle_ms':100,'direction':'tx'})
    larger=create('messages',{'name':'Eight byte command','interface_id':logical['id'],'hardware_interface_id':port['id'],'dlc':8,'cycle_ms':100,'direction':'tx'})
    from backend.nis.engineering.capacity import service as capacity_module
    resolve = capacity_module.simulation_parameters_for_protocol
    resolutions = []
    def counted(*args):
        resolutions.append(args[0])
        return resolve(*args)
    monkeypatch.setattr(capacity_module, 'simulation_parameters_for_protocol', counted)
    calculator=CapacityTimingService(current_project_id())
    results=calculator.calculate(persist=False)['results']
    metric=next(row for row in results['messages'] if row['message_id']==message['id'])
    assert metric['capacity_verified'] is False and metric['hardware_evidence'] is False
    assert metric['average_load_percent'] is None
    scenario=metric['simulation_capacity']
    assert scenario['average_load_percent']==pytest.approx(84/19200/.1*100,abs=.0001)
    assert not scenario['hardware_evidence'] and not scenario['functional_timing_accepted']
    assert results['overview']['capacity_verified'] is False
    assert len(resolutions)==1
    larger_metric=next(row for row in results['messages'] if row['message_id']==larger['id'])
    assert larger_metric['simulation_capacity']['average_load_percent']==pytest.approx(124/19200/.1*100,abs=.0001)
    changed=service.get()['parameters']
    group=changed['simulation_parameter_assumptions']['lin']
    group['values']['lin_bitrate_bps']=9600
    group['provenance']['lin_bitrate_bps']['value']=9600
    service.save_parameters(changed)
    repeated=calculator.calculate(persist=False)['results']
    assert len(resolutions)==2
    repeated_metric=next(row for row in repeated['messages'] if row['message_id']==message['id'])
    assert repeated_metric['simulation_capacity']['average_load_percent']==pytest.approx(84/9600/.1*100,abs=.0001)
    assert repeated_metric['hardware_evidence'] is False
from backend.nis.engineering.capacity.service import parameters_for_protocol
from backend.nis.workflow.services.service import WorkflowStatusService
from backend.nis.engineering.projects.project_context import current_project_id


LIN_CONTEXT={**{'lin_'+key:'synthetic-actual-'+key for key in
    ('revision','device_source','binding_source','physical_source','ldf_source','encoding_source',
     'schedule_source','capacity_source','acceptance_source','commander_node_id')},
    'lin_edition':'LIN_2_2A_2010','lin_physical_profile':'LIN_2_2A_SINGLE_WIRE',
    'lin_node_role':'COMMANDER','lin_frame_kind':'UNCONDITIONAL','lin_bitrate_bps':19200}


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
    p = mixed(); p['technology_parameters'] = {'lin': reviewed({**LIN_CONTEXT, 'cycle_ms': 50})}
    lin = parameters_for_protocol('LIN', p, network_id='lin-1', confirmed_parameters=p)
    assert lin['bitrate'] == 19200 and lin['cycle_ms'] == 50 and lin['_rate_evidenced']
    assert parameters_for_protocol('CAN_FD', p, confirmed_parameters=p)['bitrate'] == 2_000_000
    assert 'bitrate' not in parameters_for_protocol('ETHERNET', p, confirmed_parameters=p)


def test_modified_or_proposed_group_cannot_reuse_old_confirmation():
    p = mixed(); p['technology_parameters'] = {'lin': reviewed(dict(LIN_CONTEXT))}
    p['technology_parameters']['lin']['values']['lin_bitrate_bps'] = 9600
    assert not parameters_for_protocol('LIN', p, confirmed_parameters=p)['_rate_evidenced']
    p['technology_parameters']['lin']['provenance']['lin_bitrate_bps']['value'] = 9600
    p['technology_parameters']['lin']['provenance']['lin_bitrate_bps']['status'] = 'REVIEW_REQUIRED'
    assert not parameters_for_protocol('LIN', p, confirmed_parameters=p)['_rate_evidenced']


def test_explicit_network_rate_overrides_the_confirmed_group():
    p = mixed(); p['technology_parameters'] = {'lin': reviewed(dict(LIN_CONTEXT))}; p['networks'][0]['lin_bitrate_bps'] = 9600
    assert parameters_for_protocol('LIN', p, network_id='lin-1', confirmed_parameters=p)['bitrate'] == 9600


@pytest.mark.parametrize('values', [{'bitrate': 2_000_000}, {'bitrate': 19200, 'data_bitrate': 2_000_000}, {'bitrate': float('nan')}, {'bitrate': True}])
def test_invalid_or_foreign_lin_group_rejected(values):
    p = mixed(); p['technology_parameters'] = {'lin': reviewed(values)}
    with pytest.raises(ValueError): WorkflowStatusService._validate_parameter_reviews(p, mixed())


def test_valid_group_roundtrip_preserves_inventory_and_invalidates_dependents():
    service = WorkflowStatusService(current_project_id()); base = mixed(); service.save_parameters(base)
    service.mark_changed('capacity_timing', 'Testberechnung vorhanden', status='COMPLETE')
    changed = deepcopy(base); changed['technology_parameters'] = {'lin': reviewed(dict(LIN_CONTEXT))}
    saved = service.save_parameters(changed)
    assert saved['parameters']['networks'] == base['networks']
    assert saved['parameters']['technology'] == 'can_fd'
    assert service.get()['parameters']['technology_parameters']['lin']['values']['lin_bitrate_bps'] == 19200
    assert saved['statuses']['capacity_timing'] == 'OUTDATED'


def test_unconfirmed_group_cannot_be_saved_as_confirmed():
    p = mixed(); p['technology_parameters'] = {'lin': {'values': dict(LIN_CONTEXT), 'provenance': {}}}
    with pytest.raises(ValueError, match='bestätigt'): WorkflowStatusService._validate_parameter_reviews(p, mixed())


def test_individually_confirmed_partial_group_is_preserved_without_capacity_approval():
    service = WorkflowStatusService(current_project_id())
    base = mixed()
    service.save_parameters(base)
    partial = {**base, 'technology_parameters': {'lin': reviewed({'lin_bitrate_bps': 19200})}}
    saved = service.save_parameters(partial)['parameters']
    assert saved['technology_parameters']['lin']['values'] == {'lin_bitrate_bps': 19200}
    assert saved['networks'] == base['networks']
    resolved = parameters_for_protocol('LIN', saved, network_id='lin-1', confirmed_parameters=saved)
    assert resolved['lin_bitrate_bps'] == 19200
    assert not resolved['_rate_evidenced']
    assert any(item['code'] == 'TECHNOLOGY_PARAMETER_MISSING' for item in resolved['_rate_findings'])


def test_parameter_artifact_reads_confirmed_primary_group_and_allows_signed_profile_values():
    parameters = {**mixed(), 'technology': 'lin', 'technology_parameters': {'lin': reviewed(dict(LIN_CONTEXT))}}
    for key in ('bitrate', 'arbitration_bitrate', 'data_bitrate'):
        parameters.pop(key)
    check = WorkflowStatusService._parameter_artifact_check(parameters)
    assert check['complete'], check
    parameters = {**mixed(), 'clock_offset_ms': -2}
    check = WorkflowStatusService._parameter_artifact_check(parameters)
    assert check['complete'], check


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


def test_parameter_artifact_accepts_valid_historical_can_fd_nominal_alias():
    parameters = mixed()
    parameters.pop('arbitration_bitrate')
    parameters.pop('defaults_source')
    parameters['bitrate'] = 500_000
    assert WorkflowStatusService._parameter_artifact_check(parameters)['complete']
    parameters['bitrate'] = 2_000_000
    assert not WorkflowStatusService._parameter_artifact_check(parameters)['complete']


@pytest.mark.parametrize('scoped', [False, True])
@pytest.mark.parametrize('technology,values,aliases', [
    ('can', {'bitrate_bps': 500_000}, {'bitrate': 500_000}),
    ('can_fd', {'nominal_bitrate_bps': 500_000, 'data_bitrate_bps': 2_000_000},
     {'arbitration_bitrate': 500_000, 'data_bitrate': 2_000_000}),
])
def test_owned_canonical_rates_reach_consumers_with_their_confirmation(scoped, technology, values, aliases):
    parameters = {key: value for key, value in mixed().items()
                  if key not in {'bitrate', 'arbitration_bitrate', 'data_bitrate'}}
    parameters['technology'] = technology
    group = reviewed(values)
    if scoped:
        parameters['technology_parameters'] = {technology: group}
    else:
        parameters.update(values, parameter_provenance=group['provenance'])
    before = deepcopy(parameters)
    result = parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)
    assert result['_rate_evidenced'] is True
    assert all(result[key] == value for key, value in aliases.items())
    assert WorkflowStatusService._parameter_artifact_check(parameters)['complete']
    assert parameters == before
    proof = group['provenance'][next(iter(values))]
    proof['technology'] = 'ethernet'
    assert not parameters_for_protocol(technology, parameters, confirmed_parameters=parameters)['_rate_evidenced']


def test_rate_alias_conflict_remains_visible_and_blocks_computation():
    parameters = {'technology': 'can', 'bitrate_bps': 500_000, 'bitrate': 250_000}
    result = parameters_for_protocol('CAN', parameters, confirmed_parameters=parameters)
    assert result['bitrate'] == 250_000 and result['bitrate_bps'] == 500_000
    assert not result['_rate_evidenced']
    assert any(item['code'] == 'TECHNOLOGY_PARAMETER_CONFLICT' for item in result['_rate_findings'])


def test_parameter_artifact_needs_data_phase_until_brs_is_explicitly_disabled():
    parameters = {**mixed(), 'bitrate': 500_000}
    parameters.pop('data_bitrate')
    parameters.pop('defaults_source')
    assert not WorkflowStatusService._parameter_artifact_check(parameters)['complete']
    parameters['can_fd_brs'] = False
    assert WorkflowStatusService._parameter_artifact_check(parameters)['complete']


@pytest.mark.parametrize('values,code', [
    ({'bitrate': 2_000_000}, 'TECHNOLOGY_PARAMETER_OUT_OF_RANGE'),
    ({'bitrate': 19200, 'data_bitrate': 2_000_000}, 'TECHNOLOGY_RATE_MODEL_MISMATCH'),
    ({'bitrate': 19200, 'lin_bitrate_bps': 9600}, 'TECHNOLOGY_PARAMETER_CONFLICT'),
])
def test_http_invalid_native_parameter_review_returns_400_without_modifying_project(values, code):
    from backend.nis.app import create_app
    client = create_app(testing=True).test_client()
    client.environ_base['HTTP_X_PROJECT_ID'] = current_project_id()
    service = WorkflowStatusService(current_project_id())
    service.save_parameters(mixed())
    before = client.get('/api/engineering/workflow/parameters').get_json()
    changed = {**before['parameters'], 'technology_parameters': {'lin': reviewed(values)}}
    response = client.patch('/api/engineering/workflow/parameters', json={
        'expected_token': before['edit_token'], 'parameters': changed})
    assert response.status_code == 400, response.get_data(as_text=True)
    assert code in response.get_json()['error']
    after = client.get('/api/engineering/workflow/parameters').get_json()
    assert after == before


@pytest.mark.parametrize('technology,source_field', [('i2c','i2c_device_source'),('modbus_rtu','mr_device_source')])
def test_unresolved_parameter_artifact_exports_its_native_actionable_findings(technology, source_field):
    parameters = {**mixed(), 'technology': technology}
    parameters.pop('data_bitrate')
    parameters.pop('arbitration_bitrate')
    parameters['bitrate'] = 100000 if technology == 'i2c' else 9600
    check = WorkflowStatusService._parameter_artifact_check(parameters)
    assert not check['complete']
    assert check['required'][source_field] is False
    assert any(f['code'] == 'TECHNOLOGY_PARAMETER_MISSING' and f.get('parameter') == source_field
               for f in check['profile_findings'])



def test_current_parameter_review_endpoint_is_read_only_and_project_scoped():
    from backend.nis.app import create_app
    from uuid import uuid4
    client=create_app(testing=True).test_client()
    project='parameter-review-'+uuid4().hex
    headers={'X-Project-ID':project}
    before=client.get('/api/engineering/workflow/parameters',headers=headers).get_json()
    review=client.get('/api/engineering/workflow/parameters/review',headers=headers)
    assert review.status_code==200,review.get_json()
    result=review.get_json()
    assert result['project_id']==before['project_id'] and result['edit_token']==before['edit_token']
    assert result['source']=='CURRENT_CANONICAL_MODEL' and result['findings']==[]
    after=client.get('/api/engineering/workflow/parameters',headers=headers).get_json()
    assert after==before
