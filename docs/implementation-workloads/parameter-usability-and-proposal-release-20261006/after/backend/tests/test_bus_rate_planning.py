"""Rates come from the exact profile; simulation candidates never approve hardware."""
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.engineering.capacity.dimensioning import bus_rate_plan
from backend.nis.engineering.capacity.service import parameters_for_protocol
from backend.nis.communication.catalog import simulation_parameter_values


def message(period=10):
    return {'id': 'frame', 'dlc': 8, 'cycle_ms': period}


@pytest.mark.parametrize('technology,key,value', [('lin','lin_bitrate_bps',19200),
    ('can_fd','arbitration_bitrate',500000),('can_fd','data_bitrate',2000000),('ethernet','bitrate',1000000000),
    ('modbus_rtu','bitrate',19200),('ethercat','bitrate',100000000)])
def test_registered_simulation_rate_is_not_a_numeric_input_lower_bound(technology,key,value):
    fields={item['key']:item for item in registry.parameter_fields(technology)}
    assert fields[key]['simulation_default']==value
    assert fields[key]['simulation_default_provenance']['hardware_evidence'] is False


def test_lin_conditional_button_matches_the_requested_starter_and_keeps_physical_minimum():
    fields={item['key']:item for item in registry.parameter_fields('lin')}
    assert fields['lin_bitrate_bps']['conditional_defaults'][0]['value']==19200
    assert registry.profile('lin')['parameter_alias_limits']['bitrate']['minimum']==1000
    assert registry.validate_parameters('lin', {'lin_bitrate_bps':2000000})['status']=='INVALID'


def test_can_fd_starter_has_consistent_brs_data_clock_and_capability():
    values=registry.profile('can_fd')['simulation_defaults']['values']
    assert values['can_fd_brs'] is True
    assert values['can_clock_hz']/(values['can_fd_data_prescaler']*(1+values['can_fd_data_tseg1_tq']+values['can_fd_data_tseg2_tq']))==2000000
    assert registry.validate_parameters('can_fd',values)['status']=='VALID'


def test_all_registered_primary_bus_rates_have_meaningful_protocol_owned_scenarios():
    for profile in registry.profiles():
        values = simulation_parameter_values(profile['id'], profile)
        for key in (profile.get('rate_model') or {}).get('fields', []):
            if key not in values:
                continue
            assert values[key]['value'] > 1, (profile['id'], key, values[key])
            assert values[key]['hardware_evidence'] is False
            assert values[key]['technology'] == profile['id']


@pytest.mark.parametrize('technology,key,rate', [
    ('5g','bitrate_bps',100000000), ('can_aerospace','bitrate_bps',500000),
    ('ccp','bitrate_bps',500000), ('can_xl','data_bitrate_bps',10000000),
    ('iec60870_5_101','iec101_baud_bps',19200), ('lonworks','lw_network_bitrate_bps',78125),
    ('lvds','lv_lane_bps',100000000), ('mipi_csi2','cs_lane_bitrate_bps',160000000),
    ('sampled_values','sv_link_bps',100000000), ('sercos_iii','sercos_link_bps',100000000),
    ('spacewire','spw_tx_bps',10000000), ('tsn','tn_link_bps',1000000000),
    ('wireless_m_bus','wm_data_bps',16384),
])
def test_device_dependent_rates_are_explicit_marked_same_protocol_comparisons(technology,key,rate):
    proposal = simulation_parameter_values(technology, registry.profile(technology))[key]
    assert proposal['value'] == rate
    assert proposal['basis'] == 'COMPARABLE_PROTOCOL_SCENARIO'
    assert proposal['reference_source'].endswith(f'/{technology}/profile.json')
    assert proposal['hardware_evidence'] is False


def test_can_xl_comparison_uses_its_own_shared_prescaler_and_native_phy():
    profile = registry.profile('can_xl')
    values = profile['simulation_defaults']['values']
    assert values['can_prescaler'] == values['can_xl_data_prescaler']
    assert values['can_clock_hz'] / (values['can_prescaler'] * (1 + values['can_tseg1_tq'] + values['can_tseg2_tq'])) == 500000
    assert values['can_clock_hz'] / (values['can_xl_data_prescaler'] * (1 + values['can_xl_data_tseg1_tq'] + values['can_xl_data_tseg2_tq'])) == 10000000
    assert values['can_xl_phy'] == 'CAN_SIC_XL'
    assert registry.validate_parameters('can_xl', values)['status'] == 'VALID'


@pytest.mark.parametrize('technology', ['lin', 'ethernet', 'can_fd', 'can_xl', '5g'])
def test_active_scenario_defaults_obey_native_dependencies_without_populating_inactive_fields(technology):
    proposals = simulation_parameter_values(technology, registry.profile(technology))
    values = {key: proof['value'] for key, proof in proposals.items() if proof.get('applicable') is not False}
    report = registry.validate_parameters(technology, values)
    if technology == 'lin':
        assert report['status'] == 'UNVERIFIED'
        references = {field['native_key'] for field in registry.parameter_fields(technology)
                      if field['value_role'] in {'EVIDENCE', 'REFERENCE'}}
        assert report['findings']
        assert all(finding['code'] == 'TECHNOLOGY_PARAMETER_MISSING'
                   and (finding.get('parameter') or finding['message'].split()[0]) in references
                   for finding in report['findings'])
    else:
        assert report['status'] == 'VALID'
    project = registry.simulation_defaults_for_project({'technology': technology})
    group = project['simulation_parameter_assumptions'][technology]
    fields = registry.parameter_fields(technology)
    for field in fields:
        if field['simulation_default_provenance'].get('applicable') is False:
            assert field['key'] not in group['values']
            assert field['not_applicable_when']
    assert all(proof['hardware_evidence'] is False for proof in group['provenance'].values())


def test_missing_defaults_are_project_values_and_keep_explicit_and_edited_values():
    original={'technology':'lin','industry':'automotive','networks':[{'id':'l','technology':'LIN'},{'id':'c','technology':'CAN_FD'}],
              'technology_parameters':{'lin':{'values':{'lin_bitrate_bps':9600},'provenance':{}}},
              'simulation_parameter_assumptions':{'can_fd':{'values':{'can_clock_hz':80000000},'provenance':{'can_clock_hz':{'value':80000000}}}}}
    before=deepcopy(original)
    result=registry.simulation_defaults_for_project(original)
    assert original==before and result['networks']==original['networks']
    assert 'lin_bitrate_bps' not in result['simulation_parameter_assumptions']['lin']['values']
    assert result['simulation_parameter_assumptions']['can_fd']['values']['can_clock_hz']==80000000
    assert result['simulation_parameter_assumptions']['can_fd']['values']['data_bitrate']==2000000
    assert not parameters_for_protocol('CAN_FD',result,confirmed_parameters=result)['_rate_evidenced']
    assert registry.simulation_defaults_for_project(result)==result


def test_comparison_uses_same_protocol_reviewed_network_and_marks_origin():
    parameters={'technology':'rs485','networks':[{'id':'serial-ref','technology':'rs485','rs485_bitrate_bps':19200,
        'parameter_provenance':{'rs485_bitrate_bps':{'source':'USER_CONFIRMED','status':'CONFIRMED','value':19200}}},
        {'id':'foreign','technology':'can_fd','rs485_bitrate_bps':2000000,
         'parameter_provenance':{'rs485_bitrate_bps':{'source':'USER_CONFIRMED','status':'CONFIRMED','value':2000000}}}]}
    result=registry.simulation_defaults_for_project(parameters)
    group=result['simulation_parameter_assumptions']['rs485']
    assert group['values']['rs485_bitrate_bps']==19200
    assert group['provenance']['rs485_bitrate_bps']['basis']=='COMPARABLE_PROJECT_NETWORK'
    assert group['provenance']['rs485_bitrate_bps']['comparable_network_ids']==['serial-ref']
    assert group['provenance']['rs485_bitrate_bps']['hardware_evidence'] is False


def test_rate_upgrade_respects_native_limit_and_complete_wire_load():
    plan=bus_rate_plan('lin',[message()],{},industry='automotive',target_load_percent=63)
    assert plan['selected_values']['lin_bitrate_bps']==20000
    assert plan['load_percent']==pytest.approx(62)
    assert plan['hardware_evidence'] is False and plan['functional_timing_accepted'] is False
    assert max(item['values']['lin_bitrate_bps'] for item in plan['candidates'])<=20000
    faster=bus_rate_plan('can_fd',[message(.3)],{},industry='automotive')
    assert faster['selected_values']['arbitration_bitrate']==1000000
    assert faster['selected_values']['data_bitrate']==2000000


def test_lin_wire_planning_without_sources_keeps_actual_estimator_unverified_and_rejects_invalid_phy():
    from backend.nis.communication.technologies.lin.timing import estimate_frame, estimate_planning_frame
    from backend.nis.communication.catalog import PARAMETER_UI_ALIASES
    values = {PARAMETER_UI_ALIASES.get(key, key): proof['value']
              for key, proof in simulation_parameter_values('lin', registry.profile('lin')).items()
              if proof.get('applicable') is not False and proof['value'] is not None}
    values.update(bitrate=19200)
    # This assertion isolates reference gaps: the existing strict validator and
    # actual-device estimator must never turn them into confirmed evidence.
    for key in ('lin_revision', 'lin_ldf_source', 'lin_commander_node_id'):
        assert key not in values
    assert registry.validate_parameters('lin', values)['status'] == 'UNVERIFIED'
    actual = estimate_frame('LIN', 1, values)
    scenario = estimate_planning_frame('LIN', 1, values)
    assert not actual.transmission_time_available
    assert scenario.transmission_time_available
    assert scenario.frame_bits == actual.frame_bits == 54
    assert scenario.transmission_time_s == pytest.approx(54 / 19200)
    for patch in ({'lin_bitrate_bps':2000000}, {'lin_node_count':200},
                  {'lin_physical_profile':'REGISTERED_PHY'}, {'lin_data_octets':7}):
        assert not estimate_planning_frame('LIN', 1, {**values, **patch}).transmission_time_available


def test_overloaded_lin_proposes_only_selected_industry_paths_and_never_changes_bus():
    parameters={'industry':'automotive','technology':'lin'}; before=deepcopy(parameters)
    plan=bus_rate_plan('lin',[message()],parameters,industry='automotive')
    assert plan['status']=='BUS_ALTERNATIVE_PROPOSED'
    assert {item['technology'] for item in plan['alternatives']} >= {'can','can_fd'}
    assert all(item['industry']=='automotive' and item['hardware_change_required'] for item in plan['alternatives'])
    assert parameters==before
    unknown=bus_rate_plan('lin',[message()],parameters,industry=None)
    assert unknown['status']=='CAPACITY_INSUFFICIENT' and unknown['alternatives']==[]
    industrial=bus_rate_plan('lin',[message()],parameters,industry='industrial_automation')
    assert all(item['technology'] not in {'can_fd','can','lin'} for item in industrial['alternatives'])


def test_hardware_capability_and_unbounded_traffic_never_receive_a_false_fit():
    parameters={'technology_parameters':{'can_fd':{'values':{'can_fd_transceiver_max_bps':1000000}}}}
    plan=bus_rate_plan('can_fd',[message(.3)],parameters)
    assert not plan['selected_values']
    event={'id':'event','dlc':8,'configuration':{'communication_contract':{'transmission':{'mode':'EVENT','trigger':'on_change'}}}}
    assert bus_rate_plan('lin',[event],{})['status']=='TRAFFIC_UNRESOLVED'


def test_sufficient_current_defaults_are_kept_and_controller_clock_is_preserved_during_upgrade():
    for technology, key, rate in [('lin','lin_bitrate_bps',19200),('ethernet','bitrate',1000000000)]:
        result=bus_rate_plan(technology,[message(100)],{})
        assert result['selected_values'][key]==rate
    actual=deepcopy(registry.profile('can_fd')['simulation_defaults']['values'])
    actual.update(can_clock_hz=80000000,can_prescaler=10,can_fd_data_prescaler=2)
    from backend.nis.communication.catalog import PARAMETER_UI_ALIASES
    actual={PARAMETER_UI_ALIASES.get(key,key):value for key,value in actual.items()}
    parameters={'technology_parameters':{'can_fd':{'values':actual}}}
    result=bus_rate_plan('can_fd',[message(.3)],parameters)
    assert result['selected_values']['arbitration_bitrate']==1000000
    assert result['selected_values']['can_clock_hz']==80000000
    assert result['selected_values']['can_prescaler']==4
    assert result['selected_values']['can_fd_data_prescaler']==2
    assert parameters['technology_parameters']['can_fd']['values']==actual


@pytest.mark.parametrize('technology,key', [('rs422','rs422_bitrate_bps'),('rs485','rs485_bitrate_bps'),('spi','bitrate')])
def test_unqualified_device_rate_uses_a_marked_same_protocol_reference_scenario(technology,key):
    fields={item['key']:item for item in registry.parameter_fields(technology)}
    assert fields[key]['simulation_default']==10000000
    proof=fields[key]['simulation_default_provenance']
    assert proof['basis']=='COMPARABLE_PROTOCOL_SCENARIO'
    assert proof['technology']==technology and proof['hardware_evidence'] is False
    assert '/'+technology+'/' in proof['reference_source']


def test_http_defaults_save_to_project_file_and_reject_stale_revision():
    from backend.nis.app import create_app
    client=create_app(testing=True).test_client(); headers={'X-Project-ID':'defaults-'+uuid4().hex}
    before=client.get('/api/engineering/workflow/parameters',headers=headers).get_json()
    payload={'expected_token':before['edit_token'],'technologies':['lin','can_fd']}
    response=client.post('/api/engineering/workflow/parameters/defaults',headers=headers,json=payload)
    assert response.status_code==200,response.get_json()
    saved=client.get('/api/engineering/workflow/parameters',headers=headers).get_json()
    assert saved['parameters']['simulation_parameter_assumptions']['lin']['values']['lin_bitrate_bps']==19200
    document=client.get('/api/engineering/workflow/parameters/user-defined-values',headers=headers).get_json()
    assert document is not None and saved['parameter_storage']['source']=='PROJECT_USER_DEFINED_VALUES'
    assert client.post('/api/engineering/workflow/parameters/defaults',headers=headers,json=payload).status_code==409
    assert client.get('/api/engineering/workflow/parameters',headers=headers).get_json()==saved
