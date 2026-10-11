"""NB-IoT native grants, RF scope and negotiated NAS edges; synthetic evidence."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.nb_iot import rules as NB

def actual():
    x={'nbi_'+k:'synthetic-actual-'+k for k in NB.REQUIRED}
    x.update(nbi_edition=NB.EDITION,nbi_rat='EUTRA_TERRESTRIAL',nbi_category='NB1',nbi_role='UE',
        nbi_direction='UPLINK',nbi_deployment='STANDALONE',nbi_duplex='HD_FDD_TYPE_B')
    return x

def grant(tones=1,spacing=15):
    slots={1:16,3:8,6:4,12:2}[tones];slot=2 if spacing==3.75 else .5
    return {**actual(),'nbi_channel':'NPUSCH_1','nbi_grant_kind':'DCI_UNICAST','nbi_scs_khz':spacing,
        'nbi_grid_tones':48 if spacing==3.75 else 12,'nbi_slot_ms':slot,'nbi_tones':tones,
        'nbi_tone_index':0 if tones==1 else 12 if tones==3 else 16 if tones==6 else 18,
        'nbi_first_tone':0,'nbi_ru_slots':slots,'nbi_ru_ms':slots*slot,'nbi_ru_index':0,'nbi_ru_count':1,
        'nbi_rep_index':0,'nbi_repetitions':1,'nbi_mcs_index':0,'nbi_tbs_index':0,'nbi_tb_bits':16,
        'nbi_ul_tb_cap_bits':1000,'nbi_modulation':'BPSK'if tones==1 else'QPSK'}

def downlink():
    return {**actual(),'nbi_direction':'DOWNLINK','nbi_channel':'NPDSCH_UNICAST','nbi_grant_kind':'DCI_UNICAST',
        'nbi_scs_khz':15,'nbi_grid_tones':12,'nbi_modulation':'QPSK','nbi_mcs_index':0,'nbi_tbs_index':0,
        'nbi_sf_index':0,'nbi_sf_count':1,'nbi_rep_index':0,'nbi_repetitions':1,'nbi_tb_bits':16,'nbi_dl_tb_cap_bits':680}

def status(x):return registry.validate_parameters('nb_iot',x)['status']

def test_nbiot_own_rate_and_payload_are_not_can_ethernet_ltem_or_published_peak():
    fields=registry.parameter_fields('nb_iot');keys=[f['key']for f in fields]
    assert len(keys)==len(set(keys));assert not set(NB.REMOVED)&set(keys)
    assert registry.parameter_defaults_review('nb_iot')['values']=={}
    assert registry.profile('nb_iot')['domain']=='generic_networking'
    assert registry.profile('nb_iot')['capacity_evidence']['status']=='MODEL_MISSING'
    assert status(actual())=='VALID'
    for patch in ({'bitrate_bps':250000},{'bitrate':250000},{'mtu_bytes':1500},{'retry_limit':3},
        {'ltm_category':'M1'},{'vlan_id':0},{'queue_size':256},{'local_timing_evidence':{'technology':'i2c'}}):
        assert status({**actual(),**patch})=='INVALID'
    for key in('payload_bytes','nbi_band','nbi_tones','nbi_ru_count','nbi_ue_ref','nbi_t3412_raw','nbi_edrx_seconds','nbi_dl_16qam_supported'):
        f=next(f for f in fields if f['key']==key);assert 'default'not in f;assert not f.get('conditional_defaults')

@pytest.mark.parametrize('field',registry.parameter_fields('nb_iot'),ids=lambda f:f['key'])
def test_nbiot_each_declared_type_and_own_bounds(field):
    bad='not-a-number'if field['type']=='number'else 1
    assert status({**actual(),field['key']:bad})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('tones,spacing,slots,ms',[(1,3.75,16,32),(1,15,16,8),(3,15,8,4),(6,15,4,2),(12,15,2,1)])
def test_nbiot_single_and_multi_tone_rus_not_channel_bandwidth_or_application_cycle(tones,spacing,slots,ms):
    x=grant(tones,spacing);assert status(x)=='VALID';assert x['nbi_ru_slots']==slots;assert x['nbi_ru_ms']==ms
    for patch in ({'nbi_ru_slots':slots+1},{'nbi_ru_ms':ms+.1},{'nbi_slot_ms':1},
        {'nbi_channel_khz':180},{'nbi_grid_khz':200},{'nbi_scs_khz':7.5},{'nbi_grid_tones':6}):assert status({**x,**patch})=='INVALID'
    if tones>1:assert status({**x,'nbi_scs_khz':3.75})=='INVALID'

@pytest.mark.parametrize('spacing,index,tones,start',[(3.75,47,1,47),(15,11,1,11),(15,15,3,9),(15,17,6,6),(15,18,12,0)])
def test_nbiot_contiguous_subcarrier_indices_and_reserved_fields(spacing,index,tones,start):
    x={**grant(tones,spacing),'nbi_tone_index':index,'nbi_first_tone':start};assert status(x)=='VALID'
    assert status({**x,'nbi_first_tone':start+1})=='INVALID'
    assert status({**x,'nbi_tone_index':48 if spacing==3.75 else 19})=='INVALID'

@pytest.mark.parametrize('index,count',[(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,8),(7,10)])
def test_nbiot_uplink_resource_count_and_repetitions_are_grant_encoded(index,count):
    x=grant(12);x.update(nbi_ru_index=index,nbi_ru_count=count,nbi_tb_bits=[16,32,56,88,120,152,208,256][index],
        nbi_rep_index=7,nbi_repetitions=128);assert status(x)=='VALID'
    for patch in ({'nbi_ru_count':count+1},{'nbi_repetitions':127},{'nbi_rep_index':8}):assert status({**x,**patch})=='INVALID'

@pytest.mark.parametrize('mcs,mod,index,bits',[(0,'BPSK',0,16),(1,'BPSK',2,32),(2,'QPSK',1,24),(3,'QPSK',3,40),(10,'QPSK',10,144)])
def test_nbiot_single_tone_mcs_does_not_always_equal_tbs_index(mcs,mod,index,bits):
    x=grant();x.update(nbi_mcs_index=mcs,nbi_modulation=mod,nbi_tbs_index=index,nbi_tb_bits=bits)
    assert status(x)=='VALID';assert status({**x,'nbi_tb_bits':bits+1})=='INVALID'
    assert status({**x,'nbi_mcs_index':11})=='INVALID'

def test_nbiot_nb1_nb2_and_optional_r17_qam_capabilities_do_not_copy_m1_m2_limits():
    x={**actual(),'nbi_dl_tb_cap_bits':680,'nbi_soft_channel_bits':2112,'nbi_ul_tb_cap_bits':1000,'nbi_layer2_cap_bytes':4000}
    assert status(x)=='VALID';assert status({**x,'nbi_dl_tb_cap_bits':1000})=='INVALID'
    assert status({**x,'nbi_two_harq_supported':True})=='INVALID'
    x.update(nbi_category='NB2',nbi_dl_16qam_supported=False,nbi_dl_tb_cap_bits=2536,nbi_soft_channel_bits=6400,
        nbi_ul_tb_cap_bits=2536,nbi_layer2_cap_bytes=8000)
    assert status(x)=='VALID';assert status({**x,'nbi_dl_tb_cap_bits':4968})=='INVALID'
    x.update(nbi_dl_16qam_supported=True,nbi_dl_tb_cap_bits=4968,nbi_soft_channel_bits=12800,nbi_layer2_cap_bytes=12000)
    assert status(x)=='VALID';assert status({**x,'nbi_dl_tb_cap_bits':4008})=='INVALID'
    x.pop('nbi_dl_16qam_supported');assert status(x)=='UNVERIFIED'
    x={**actual(),'nbi_category':'NB2','nbi_harq_processes':2,'nbi_two_harq_supported':True};assert status(x)=='VALID'
    assert status({**x,'nbi_two_harq_supported':False})=='INVALID'

def test_nbiot_largest_qam16_blocks_and_sparse_table_entries_require_own_actual_capability():
    x=grant(12);x.update(nbi_category='NB2',nbi_ul_16qam_supported=True,nbi_qam16_configured=True,
        nbi_modulation='16QAM',nbi_mcs_index=15,nbi_qam16_index=7,nbi_tbs_index=21,nbi_ru_index=4,
        nbi_ru_count=5,nbi_tb_bits=2536,nbi_ul_tb_cap_bits=2536)
    assert status(x)=='VALID'
    for patch in ({'nbi_ul_16qam_supported':False},{'nbi_category':'NB1'},{'nbi_ru_index':7,'nbi_ru_count':10},
        {'nbi_repetitions':2},{'nbi_mcs_index':14},{'nbi_tb_bits':2537}):assert status({**x,**patch})=='INVALID'
    d=downlink();d.update(nbi_category='NB2',nbi_dl_16qam_supported=True,nbi_qam16_configured=True,
        nbi_modulation='16QAM',nbi_mcs_index=15,nbi_qam16_index=7,nbi_tbs_index=21,
        nbi_sf_index=7,nbi_sf_count=10,nbi_tb_bits=4968,nbi_dl_tb_cap_bits=4968)
    assert status(d)=='VALID';assert status({**d,'nbi_tb_bits':2536})=='INVALID'
    assert status({**d,'nbi_deployment':'INBAND_SAME_PCI'})=='INVALID'
    d.update(nbi_deployment='INBAND_DIFFERENT_PCI',nbi_qam16_index=6,nbi_tbs_index=17,nbi_tb_bits=3624)
    assert status(d)=='VALID';assert status({**d,'nbi_repetitions':2})=='INVALID'

def test_nbiot_dl_and_ul_tbs_differ_and_downlink_allows2048_repetitions():
    d=downlink();d.update(nbi_mcs_index=7,nbi_tbs_index=7,nbi_sf_index=5,nbi_sf_count=6,nbi_tb_bits=680,
        nbi_rep_index=15,nbi_repetitions=2048)
    assert status(d)=='VALID';assert status({**d,'nbi_tb_bits':712})=='INVALID'
    assert status({**d,'nbi_scs_khz':3.75})=='INVALID'
    u=grant(12);u.update(nbi_mcs_index=7,nbi_tbs_index=7,nbi_ru_index=5,nbi_ru_count=6,nbi_tb_bits=712)
    assert status(u)=='VALID';assert status({**u,'nbi_tb_bits':680})=='INVALID'

@pytest.mark.parametrize('band,duplex,ul,dl',[(17,'HD_FDD_TYPE_B',710,740),(31,'HD_FDD_TYPE_B',455,465),
 (54,'TDD',1672,1672),(65,'HD_FDD_TYPE_B',1930,2120),(103,'HD_FDD_TYPE_B',787.5,757.5)])
def test_nbiot_own_bands_include17_65_103_and54_is_tdd(band,duplex,ul,dl):
    x={**actual(),'nbi_band':band,'nbi_duplex':duplex,'nbi_ns':'OTHER','nbi_carrier_mhz':ul}
    if duplex=='TDD':x.update(nbi_tdd_source='synthetic-actual-tdd',nbi_tdd_assignment=1)
    if band==65:x['nbi_band_qualification_source']='synthetic-band1-qualified'
    assert status(x)=='VALID';assert status({**x,'nbi_direction':'DOWNLINK','nbi_carrier_mhz':dl})=='VALID'
    assert status({**x,'nbi_duplex':'HD_FDD_TYPE_B'if duplex=='TDD'else'TDD','nbi_tdd_source':'synthetic-tdd'})=='INVALID'
    for invalidband in(6,27,39,40,107):assert status({**x,'nbi_band':invalidband})=='INVALID'

def test_nbiot_network_ns_us_edges_band24_gaps_and_actual_power_and_ppm_context():
    x={**actual(),'nbi_band':2,'nbi_ns':'NS_04','nbi_carrier_mhz':1850.1,'nbi_tones':1,
        'nbi_frequency_error_abs_ppm':.1,'nbi_frequency_error_source':'synthetic-relative-averaged',
        'nbi_frequency_average_slots':72,'nbi_power_class':'3','nbi_nominal_max_power_dbm':23}
    assert status(x)=='VALID'
    for patch in ({'nbi_carrier_mhz':1850},{'nbi_frequency_error_abs_ppm':.11},{'nbi_frequency_average_slots':6},
        {'nbi_nominal_max_power_dbm':26}):assert status({**x,**patch})=='INVALID'
    x.update(nbi_band=31,nbi_ns='OTHER',nbi_carrier_mhz=455,nbi_frequency_error_abs_ppm=.2)
    assert status(x)=='VALID';assert status({**x,'nbi_frequency_error_abs_ppm':.21})=='INVALID'
    b={**actual(),'nbi_band':24,'nbi_ns':'OTHER','nbi_band_qualification_source':'synthetic-regional',
        'nbi_carrier_mhz':1637.5};assert status(b)=='VALID'
    assert status({**b,'nbi_carrier_mhz':1646.5})=='VALID'
    for bad in(1637.50001,1646.49999,1626.5):assert status({**b,'nbi_carrier_mhz':bad})=='INVALID'
    p={**actual(),'nbi_band':88,'nbi_nominal_max_power_dbm':17,'nbi_power_class':'REGISTERED_POWER_CLASS',
        'nbi_registered_source':'synthetic-schema','nbi_power_source':'synthetic-band88-measurement'}
    assert status(p)=='VALID';p.pop('nbi_power_source');assert status(p)=='UNVERIFIED'

def test_nbiot_control_plane_can_be_ip_nonip_or_ethernet_but_scef_is_cp_only_nonip():
    x={**actual(),'nbi_nas_mode':'NB_S1','nbi_cp_supported':True,'nbi_ciot_path':'CONTROL_PLANE','nbi_ciot_accepted':True}
    for kind in('IPV4','IPV6','IPV4V6','NON_IP','ETHERNET'):assert status({**x,'nbi_pdn_type':kind})=='VALID'
    x.update(nbi_core_endpoint='SCEF',nbi_pdn_type='NON_IP',nbi_control_plane_only=True)
    assert status(x)=='VALID'
    for patch in ({'nbi_pdn_type':'IPV4'},{'nbi_ciot_path':'USER_PLANE','nbi_up_supported':True,'nbi_s1u_supported':True},
        {'nbi_cp_supported':False},{'nbi_ciot_accepted':False}):assert status({**x,**patch})=='INVALID'
    u={**actual(),'nbi_nas_mode':'NB_S1','nbi_ciot_path':'USER_PLANE','nbi_up_supported':True,
       'nbi_s1u_supported':True,'nbi_ciot_accepted':True};assert status(u)=='VALID'
    assert status({**u,'nbi_s1u_supported':False})=='INVALID'

@pytest.mark.parametrize('receiver,protected,seconds',[('NETWORK',False,35712000),('UE',True,35712000),('UE',False,111600)])
def test_nbiot_extended_t3412_unit6_depends_on_receiver_and_integrity(receiver,protected,seconds):
    x={**actual(),'nbi_timer_receiver':receiver,'nbi_t3412_integrity':protected,'nbi_t3412_unit':6,
        'nbi_t3412_value':31,'nbi_t3412_raw':223,'nbi_t3412_seconds':seconds,'nbi_t3412_present':True}
    assert status(x)=='VALID';assert status({**x,'nbi_t3412_seconds':seconds+1})=='INVALID'
    assert status({**x,'nbi_t3412_raw':222})=='INVALID'
    if receiver=='UE':x.pop('nbi_t3412_integrity');assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('unit,seconds',[(0,600),(1,3600),(2,36000),(3,2),(4,30),(5,60)])
def test_nbiot_t3412_units_do_not_copy_active_timer_or_ltem_values(unit,seconds):
    x={**actual(),'nbi_timer_receiver':'UE','nbi_t3412_unit':unit,'nbi_t3412_value':1,
        'nbi_t3412_raw':unit*32+1,'nbi_t3412_seconds':seconds,'nbi_t3412_present':True}
    assert status(x)=='VALID';assert status({**x,'nbi_t3412_seconds':seconds+1})=='INVALID'

def test_nbiot_timer_absence_deactivation_and_zero_are_not_all_equivalent():
    x={**actual(),'nbi_t3412_unit':7,'nbi_t3412_value':31,'nbi_t3412_raw':255,'nbi_t3412_present':False}
    assert status(x)=='VALID';assert status({**x,'nbi_t3412_present':True})=='INVALID'
    assert status({**x,'nbi_t3412_seconds':0,'nbi_timer_receiver':'UE'})=='INVALID'
    x={**actual(),'nbi_t3324_unit':7,'nbi_t3324_value':31,'nbi_t3324_raw':255,'nbi_t3324_active':False}
    assert status(x)=='VALID';assert status({**x,'nbi_t3324_seconds':0})=='INVALID'
    x.update(nbi_t3324_unit=0,nbi_t3324_value=0,nbi_t3324_raw=0,nbi_t3324_seconds=0,nbi_t3324_active=True)
    assert status(x)=='VALID'
    for unit,scale in enumerate([2,60,360,60,60,60,60]):
        z={**x,'nbi_t3324_unit':unit,'nbi_t3324_value':31,'nbi_t3324_raw':unit*32+31,'nbi_t3324_seconds':scale*31}
        assert status(z)=='VALID';assert status({**z,'nbi_t3324_seconds':scale*31+1})=='INVALID'

@pytest.mark.parametrize('code,seconds',[(2,20.48),(3,40.96),(4,20.48),(5,81.92),(6,20.48),(7,20.48),(8,20.48),
    (9,163.84),(10,327.68),(11,655.36),(12,1310.72),(13,2621.44),(14,5242.88),(15,10485.76)])
def test_nbiot_edrx_nb_mapping_and_paging_window_are_not_ltem_table(code,seconds):
    x={**actual(),'nbi_nas_mode':'NB_S1','nbi_edrx_code':code,'nbi_edrx_seconds':seconds,
       'nbi_ptw_code':15,'nbi_ptw_seconds':40.96,'nbi_edrx_raw':240+code,'nbi_edrx_granted':True,
       'nbi_timer_source':'synthetic-latest-protected-NAS-IE'}
    assert status(x)=='VALID'
    for patch in ({'nbi_edrx_seconds':seconds+1},{'nbi_ptw_seconds':20.48},{'nbi_edrx_raw':code}):assert status({**x,**patch})=='INVALID'
    x.update(nbi_ptw_code=0,nbi_ptw_seconds=2.56,nbi_edrx_raw=code);assert status(x)=='VALID'

def test_nbiot_edrx_reserved0_1_are_absent_ie_not_512_or_1024seconds():
    for code in(0,1):
        x={**actual(),'nbi_nas_mode':'NB_S1','nbi_edrx_code':code,'nbi_edrx_granted':False};assert status(x)=='VALID'
        assert status({**x,'nbi_edrx_granted':True})=='INVALID'
        assert status({**x,'nbi_edrx_seconds':5.12 if code==0 else 10.24})=='INVALID'

def test_nbiot_psm_request_is_not_grant_and_grant_is_not_immediate_downlink_or_e2e_capacity():
    x={**actual(),'nbi_nas_mode':'NB_S1','nbi_psm_requested':True};assert status(x)=='VALID'
    assert status({**x,'nbi_psm_active':True})=='UNVERIFIED'
    x.update(nbi_psm_granted=True,nbi_psm_active=True,nbi_t3324_unit=0,nbi_t3324_active=True,
        nbi_t3324_raw=0,nbi_t3324_value=0,nbi_t3324_seconds=0,
        nbi_rrc_state='IDLE',nbi_emm_state='NORMAL_SERVICE',nbi_emergency=False,nbi_timer_source='synthetic-latest-grant')
    assert status(x)=='VALID'
    for patch in ({'nbi_psm_granted':False},{'nbi_rrc_state':'CONNECTED'},{'nbi_emergency':True},
        {'nbi_t3324_unit':7},{'nbi_t3324_active':False}):assert status({**x,**patch})=='INVALID'
    x={**actual(),'nbi_nas_mode':'NB_S1','nbi_edrx_using':True,'nbi_edrx_granted':True,'nbi_edrx_code':2,
        'nbi_edrx_raw':2,'nbi_edrx_seconds':20.48,'nbi_ptw_code':0,'nbi_ptw_seconds':2.56,
        'nbi_emergency':False,'nbi_timer_source':'synthetic-current-accept'};assert status(x)=='VALID'
    assert status({**x,'nbi_emergency':True})=='INVALID'
    for key in('nbi_edrx_raw','nbi_ptw_code','nbi_ptw_seconds','nbi_edrx_seconds','nbi_timer_source'):
        assert status({k:v for k,v in x.items()if k!=key})=='UNVERIFIED'

@pytest.mark.parametrize('kind,increment',[('EMM',240),('ESM',180)])
def test_nbiot_nas_procedure_addition_does_not_modify_functional_deadline(kind,increment):
    x={**actual(),'nbi_nas_mode':'NB_S1','nbi_nas_procedure_class':kind,'nbi_nas_base_timer_s':15,
        'nbi_nas_timer_s':15+increment,'nbi_functional_bound_ms':100}
    assert status(x)=='VALID';assert status({**x,'nbi_nas_timer_s':15})=='INVALID'

def test_nbiot_standard_proposals_are_conditional_and_actual_upper_message_may_span_radio_blocks():
    f={f['key']:f for f in registry.parameter_fields('nb_iot')}
    assert {v['value']for v in f['nbi_scs_khz']['conditional_defaults']}=={3.75,15}
    assert all(p['source']and p['source_revision']and p['when']['nbi_rat']=='EUTRA_TERRESTRIAL'
       for field in f.values()for p in field.get('conditional_defaults',[]))
    x={**actual(),'payload_bytes':5000,'nbi_header_bytes':20,'nbi_packet_bytes':5020};assert status(x)=='VALID'
    assert status({**x,'nbi_packet_bytes':5000})=='INVALID'
    for key in NB.REQUIRED:
        z=actual();z.pop('nbi_'+key);assert status(z)!='VALID'
    x={**actual(),'nbi_rat':'REGISTERED_RAT','nbi_registered_source':'synthetic-NR-NTN-own-schema','nbi_carrier_mhz':2500,
       'nbi_band':103,'nbi_ns':'OTHER'};assert status(x)=='VALID'
    assert registry.profile('nb_iot')['capacity_evidence']['status']=='MODEL_MISSING'

def test_nbiot_confirmed_custom_nas_duration_zero_active_timer_and_large_encoded_message_are_preserved():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x={**actual(),'nbi_timer_receiver':'UE','nbi_t3412_integrity':True,'nbi_t3412_unit':6,
        'nbi_t3412_value':31,'nbi_t3412_raw':223,'nbi_t3412_seconds':35712000,'nbi_t3412_present':True,
        'nbi_t3324_unit':0,'nbi_t3324_value':0,'nbi_t3324_raw':0,'nbi_t3324_seconds':0,
        'payload_bytes':5000,'nbi_header_bytes':20,'nbi_packet_bytes':5020}
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'nb_iot','technology_parameters':{'nb_iot':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters)
    assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['nb_iot']['values']['bitrate_bps']=250000
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
