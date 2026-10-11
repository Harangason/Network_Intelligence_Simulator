"""UDS session, codec and selected transport rules do not copy CAN defaults."""
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.uds import rules as R
from backend.nis.engineering.capacity.calculators import estimate_frame
def actual(transport='DOIP'):
 x={'us_'+k:'synthetic-'+k for k in R.REQUIRED};x.update(us_review_profile='AUTOSAR_DCM_R25_11',us_transport=transport,**{'us_'+{'DOIP':'doip_source','CAN_ISOTP':'can_source','CANFD_ISOTP':'can_source','FLEXRAY_TP':'flexray_source','LIN_TP':'lin_source','REGISTERED_ACTUAL':'registered_source'}[transport]:'synthetic'});return x
def status(x):return registry.validate_parameters('uds',x)['status']
def test_uds_industry_neutral_application_no_implicit_can_or_4095cap():
 p=registry.profile('uds');assert p['domain']=='generic_networking'and p['default_stack']==['uds']and p['max_payload_bytes']is None
 assert p['capacity_evidence']['status']=='MODEL_MISSING'and status(actual())=='VALID'and status({})=='UNVERIFIED'
 for bad in({'bitrate':500000},{'retry_limit':3},{'nominal_bitrate_bps':500000}):assert status({**actual(),**bad})=='INVALID'
 assert estimate_frame('uds',8,actual()).to_dict()['transmission_time_s']is None
@pytest.mark.parametrize('f',registry.parameter_fields('uds'),ids=lambda f:f['key'])
def test_every_uds_field_type_and_outer_bounds(f):
 assert status({**actual(),f['key']:'wrong'if f['type']=='number'else 1})=='INVALID'
 for side,offset in [('min',-1),('max',1)]:
  if f.get(side)is not None:assert status({**actual(),f['key']:f[side]+offset})=='INVALID'
@pytest.mark.parametrize('transport',['CAN_ISOTP','CANFD_ISOTP','DOIP','FLEXRAY_TP','LIN_TP','REGISTERED_ACTUAL'])
def test_every_selected_transport_has_independent_registered_evidence(transport):
 x=actual(transport);assert status(x)=='VALID'
 x.pop('us_'+{'CAN_ISOTP':'can_source','CANFD_ISOTP':'can_source','DOIP':'doip_source','FLEXRAY_TP':'flexray_source','LIN_TP':'lin_source','REGISTERED_ACTUAL':'registered_source'}[transport]);assert status(x)=='UNVERIFIED'
@pytest.mark.parametrize('transport',['DOIP','FLEXRAY_TP','LIN_TP'])
@pytest.mark.parametrize('key',R.CAN_FIELDS)
def test_noncan_transport_forbids_can_tp_facts(transport,key):assert status({**actual(transport),'us_'+key:'synthetic'if key in('can_source','can_addressing')else 1})=='INVALID'
def test_uds_request_and_response_limits_come_from_actual_tp_and_buffers():
 x={**actual(),'us_request_bytes':10000,'us_response_bytes':5000,'us_tp_max_bytes':20000,'us_rx_buffer_bytes':10000,'us_tx_buffer_bytes':5000};assert status(x)=='VALID'
 for bad in({'us_tp_max_bytes':9999},{'us_rx_buffer_bytes':9999},{'us_tx_buffer_bytes':4999}):assert status({**x,**bad})=='INVALID'
def test_dcm_actual_seconds_and_minima_not_can_or_client_wait():
 x={**actual(),'us_p2_min_s':0,'us_p2_star_min_s':0,'us_p2_server_s':.05,'us_p2_star_server_s':5};assert status(x)=='VALID'
 for bad in({'us_p2_min_s':.001},{'us_p2_star_min_s':.001},{'us_p2_server_s':1.01},{'us_p2_star_server_s':100.01}):assert status({**x,**bad})=='INVALID'
def test_s3_default_only_without_configured_override():
 x={**actual(),'us_s3_policy':'NO_OVERRIDE','us_s3_s':5};assert status(x)=='VALID'
 assert status({**x,'us_s3_s':10})=='INVALID'
 assert status({**x,'us_s3_override_s':10})=='INVALID'
 x.update(us_s3_policy='CONFIGURED_OVERRIDE',us_s3_override_s=10,us_s3_s=10);assert status(x)=='VALID'
 assert status({**x,'us_s3_override_s':4,'us_s3_s':4})=='INVALID'
 assert status({**x,'us_s3_s':5})=='INVALID'
def test_dcm_initiation_adjustment_is_task_multiple_and_inside_maximum():
 x={**actual(),'us_task_s':.01,'us_p2_server_s':.05,'us_p2_adjust_ticks':2,'us_p2_adjust_s':.02,'us_p2_trigger_s':.03};assert status(x)=='VALID'
 for bad in({'us_p2_adjust_s':.015},{'us_p2_trigger_s':.05},{'us_p2_adjust_s':.06,'us_p2_adjust_ticks':6,'us_p2_trigger_s':0}):assert status({**x,**bad})=='INVALID'
 x.pop('us_p2_adjust_ticks');assert status(x)=='UNVERIFIED'
def test_p2star_adjustment_not_p2_and_bound_client_time():
 x={**actual(),'us_task_s':.01,'us_p2_star_server_s':5,'us_p2_star_adjust_ticks':2,'us_p2_star_adjust_s':.02,'us_p2_star_trigger_s':4.98,'us_client_p2_star_s':5.1};assert status(x)=='VALID'
 assert status({**x,'us_p2_star_trigger_s':5})=='INVALID'
 assert status({**x,'us_client_p2_star_s':4})=='INVALID'
def test_response_phase_uses_own_server_timer_not_fixed_all5seconds():
 x={**actual(),'us_p2_server_s':.05,'us_p2_star_server_s':5,'us_phase':'INITIAL_P2','us_response_start_s':.05};assert status(x)=='VALID'
 assert status({**x,'us_response_start_s':1})=='INVALID'
 assert status({**x,'us_phase':'AFTER_NRC78_P2STAR','us_response_start_s':1})=='VALID'
def test_pending_count0_disallows78_not_unlimited_and255_is_not_infinity():
 x={**actual(),'us_pending_limit':0,'us_pending_count':0};assert status(x)=='VALID'
 assert status({**x,'us_message_kind':'NEGATIVE','us_nrc':120})=='INVALID'
 assert status({**x,'us_pending_count':1})=='INVALID'
 assert status({**x,'us_pending_limit':255,'us_pending_count':256})=='INVALID'
@pytest.mark.parametrize('sid',[64,127,192,255])
def test_response_service_ranges_not_transmitted_request(sid):assert status({**actual(),'us_request_sid':sid})=='INVALID'
def request(suppress=False):return {**actual(),'us_codec_profile':'UDSONCAN_1_25_1','us_codec_source':'synthetic','us_message_kind':'REQUEST','us_request_sid':62,'us_has_subfunction':True,'us_subfunction':0,'us_suppress_positive':suppress,'us_wire_subfunction':128 if suppress else 0,'us_request_data_bytes':0,'us_request_bytes':2,'us_request_hex':'3e80'if suppress else'3e00'}
def test_suppress_flag_only_bit7_actual_service_subfunction():
 x=request(True);assert status(x)=='VALID'
 for bad in({'us_wire_subfunction':0},{'us_subfunction':128},{'us_request_hex':'3e00'},{'us_has_subfunction':False}):assert status({**x,**bad})=='INVALID'
 assert status({**request(False),'us_wire_subfunction':128})=='INVALID'
def test_no_subfunction_has_no_suppress_bit_or_extra_header():
 x={**actual(),'us_request_sid':34,'us_has_subfunction':False,'us_suppress_positive':False,'us_request_data_bytes':2,'us_request_bytes':3};assert status(x)=='VALID'
 assert status({**x,'us_suppress_positive':True})=='INVALID'
 assert status({**x,'us_request_bytes':4})=='INVALID'
def test_native_negative_header_contains_request_sid_not_positive():
 x={**actual(),'us_codec_profile':'UDSONCAN_1_25_1','us_codec_source':'synthetic','us_message_kind':'NEGATIVE','us_request_sid':34,'us_response_sid':127,'us_nrc':49,'us_response_bytes':3,'us_response_hex':'7f2231'};assert status(x)=='VALID'
 for bad in({'us_response_hex':'7f6231'},{'us_response_sid':98},{'us_nrc':0},{'us_response_bytes':2},{'us_response_hex':'7f22'}):assert status({**x,**bad})=='INVALID'
@pytest.mark.parametrize('nrc',[17,18,49,126,127])
def test_functional_negative_suppression_is_exact_list(nrc):
 x={**actual(),'us_addressing':'FUNCTIONAL','us_message_kind':'NEGATIVE','us_nrc':nrc,'us_response_sent':False};assert status(x)=='VALID'
 assert status({**x,'us_response_sent':True})=='INVALID'
 assert status({**x,'us_addressing':'PHYSICAL','us_response_sent':True})=='VALID'
def test_positive_suppression_does_not_suppress_every_negative():
 assert status({**actual(),'us_message_kind':'POSITIVE','us_suppress_positive':True,'us_response_sent':True})=='INVALID'
 assert status({**actual(),'us_message_kind':'NEGATIVE','us_suppress_positive':True,'us_nrc':120,'us_response_sent':True})=='VALID'
def session_response():return {**actual(),'us_codec_profile':'UDSONCAN_1_25_1','us_codec_source':'synthetic','us_standard_version':'ISO_2013_PLUS','us_message_kind':'POSITIVE','us_request_sid':16,'us_response_sid':80,'us_session':3,'us_session_echo':3,'us_p2_wire_raw':50,'us_p2_star_wire_raw':500,'us_p2_server_s':.05,'us_p2_star_server_s':5,'us_response_bytes':6,'us_response_hex':'5003003201f4'}
def test_session_response_2013_ms_vs10ms_and_echo():
 x=session_response();assert status(x)=='VALID'
 for bad in({'us_p2_server_s':50},{'us_p2_star_server_s':.5},{'us_session_echo':2},{'us_response_bytes':5},{'us_response_hex':'5003003200f4'}):assert status({**x,**bad})=='INVALID'
def test_2006_record_not_forced2013_timing_fields():
 x={**session_response(),'us_standard_version':'ISO_2006','us_response_bytes':3,'us_response_hex':'5003ff'}
 for k in('us_p2_wire_raw','us_p2_star_wire_raw','us_p2_server_s','us_p2_star_server_s'):x.pop(k)
 assert status(x)=='VALID'
def test_full_tp_service_and_fresh_function_result_not_positive_pdu_only():
 x={**actual(),'us_source_ms':1,'us_transport_ms':2,'us_service_ms':3,'us_e2e_ms':6,'us_deadline_ms':6,'us_age_ms':5,'us_freshness_ms':5};assert status(x)=='VALID'
 for bad in({'us_e2e_ms':2},{'us_deadline_ms':5},{'us_freshness_ms':4}):assert status({**x,**bad})=='INVALID'
 x.update(us_data_accepted=True,us_observation_source='synthetic',us_tp_verified=True,us_path_verified=True,us_service_verified=True,us_outcome='ACCEPTED');assert status(x)=='VALID'
 assert status({**x,'us_outcome':'RESPONSE_PENDING'})=='INVALID'
def test_literature_only_minima_and_conditional_s3_no_fake_transport_timeout():
 f={v['key']:v for v in registry.parameter_fields('uds')};assert f['us_s3_s']['conditional_defaults'][0]['when']['us_s3_policy']=='NO_OVERRIDE'
 for k in('us_p2_server_s','us_p2_star_server_s','us_pending_limit','us_cantp_bs','us_cantp_stmin_s','us_transport','payload_bytes'):assert 'default'not in f[k]and'conditional_defaults'not in f[k]
