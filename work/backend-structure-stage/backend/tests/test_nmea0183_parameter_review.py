"""NMEA0183 sentences/serial/port qualifiers, never NMEA2000/CAN shortcuts."""
from copy import deepcopy
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.technologies.nmea0183 import rules as NT

def actual(binding='STANDARD_SERIAL',body='GPZDA,141644.00,22,03,2002,00,00'):
    x={'nt_'+k:'synthetic-actual-'+k for k in NT.REQUIRED}
    checksum=0
    for octet in body.encode('ascii'):checksum^=octet
    address=body.split(',',1)[0];sentence=f'${body}*{checksum:02X}\r\n'
    x.update(nt_implementation='UBLOX20_HPG2',nt_version='4.11',nt_role='TALKER',nt_binding=binding,
      nt_port='UART1',nt_phy='LOGIC_UART',nt_talker_ref='synthetic-one-talker',nt_talker_count=1,
      nt_port_config_source='synthetic-port-config',nt_data_bits=8,nt_stop_bits=1,nt_parity='NONE',nt_parity_bits=0,
      nt_wire_bits_per_char=10,nt_start='$',nt_sentence_form='STANDARD',nt_address=address,nt_talker_id=address[:2],
      nt_formatter=address[2:],nt_body=body,nt_body_bytes=len(body),nt_sentence_bytes=len(sentence),
      nt_sentence=sentence,nt_checksum=checksum,nt_version_code=42,nt_limit82=True)
    if binding in NT.SERIAL:
        x.update(bitrate_bps=38400 if binding=='HIGH_SPEED_SERIAL' else 4800,nt_rx_baud_bps=38400 if binding=='HIGH_SPEED_SERIAL' else 4800)
    else:x['nt_wrapper_source']='synthetic-registered-wrapper'
    return x
def status(x):return registry.validate_parameters('nmea0183',x)['status']
def mux(port='OUT1',rate=115200):
    x=actual('DEVICE_UART');x.update(nt_implementation='PRO_MUX_1',nt_port=port,nt_phy='RS422',
      bitrate_bps=rate,nt_rx_baud_bps=rate,nt_role='LISTENER'if port.startswith('IN')else'TALKER')
    return x

def test_nmea0183_distinct_registered_transport_no_forced_marine_can_ethernet_or_payload_default():
    keys=[v['key']for v in registry.parameter_fields('nmea0183')]
    assert len(keys)==len(set(keys));assert not set(NT.REMOVED)&set(keys)
    assert registry.profile('nmea0183')['domain']=='generic_networking'
    assert registry.profile('nmea0183')['capacity_evidence']['status']=='MODEL_MISSING'
    assert registry.parameter_defaults_review('nmea0183')['values']=={}
    assert status(actual())=='VALID'
    missing=actual();missing.pop('bitrate_bps');assert status(missing)=='UNVERIFIED'
    for patch in({'bitrate_bps':250000},{'mtu_bytes':1500},{'vlan_id':0},{'queue_size':256},
       {'retry_limit':3},{'mq_qos':1},{'local_timing_evidence':{'technology':'CAN'}},
       {'nt_talker_count':2},{'nt_parity':'EVEN'},{'nt_data_bits':7}):assert status({**actual(),**patch})=='INVALID'
    for k in('payload_bytes','nt_talker_ref','nt_listener_count','nt_output_period_ms','nt_age_ms','nt_supply_v'):
        f=next(v for v in registry.parameter_fields('nmea0183')if v['key']==k)
        assert 'default'not in f;assert not f.get('conditional_defaults')

@pytest.mark.parametrize('field',registry.parameter_fields('nmea0183'),ids=lambda f:f['key'])
def test_nmea0183_each_declared_type_unit_and_own_bound(field):
    bad='not-number' if field['type']=='number' else 1
    assert status({**actual(),field['key']:bad})=='INVALID'
    for edge,offset in [('min',-1),('max',1)]:
        if field.get(edge)is not None:assert status({**actual(),field['key']:field[edge]+offset})=='INVALID'

@pytest.mark.parametrize('binding,rate',[('STANDARD_SERIAL',4800),('HIGH_SPEED_SERIAL',38400)])
def test_nmea0183_standard_and_hs_baselines_one_talker_8n1_and_receiver_match(binding,rate):
    x=actual(binding);assert status(x)=='VALID'
    x.update(nt_character_ms=10000/rate,nt_sentence_serial_ms=x['nt_sentence_bytes']*10000/rate)
    assert status(x)=='VALID';assert status({**x,'nt_listener_count':50})=='VALID'
    for patch in({'nt_rx_baud_bps':9600},{'nt_wire_bits_per_char':8},{'nt_character_ms':8000/rate},
      {'nt_sentence_serial_ms':1000/rate},{'bitrate_bps':rate+1}):assert status({**x,**patch})=='INVALID'
    field=next(v for v in registry.parameter_fields('nmea0183')if v['key']=='bitrate')
    assert any(p['when']=={'nt_binding':binding}and p['value']==rate for p in field['conditional_defaults'])

def test_nmea0183_known_primary_sentence_checksum67_complete_crlf_and_null_fields42():
    x=actual();assert x['nt_checksum']==0x67;assert status(x)=='VALID'
    for patch in({'nt_checksum':0x66},{'nt_sentence':x['nt_sentence'].replace('*67','*66')},
      {'nt_sentence':x['nt_sentence'].replace('141644','141645')},{'nt_sentence':x['nt_sentence'].rstrip()},
      {'nt_sentence':x['nt_sentence']+'\n'},{'nt_sentence':x['nt_sentence'].replace('ZDA','zda')},
      {'nt_body':x['nt_body']+',0'},{'nt_sentence_bytes':x['nt_sentence_bytes']-2},
      {'nt_talker_id':'GN'},{'nt_formatter':'GGA'}):assert status({**x,**patch})=='INVALID'
    x=actual(body='GPGLL,,,,,124924.00,V,N');assert x['nt_checksum']==0x42;assert status(x)=='VALID'
    x.update(nt_freshness_status='INVALID',nt_invalid_fix_output=True);assert status(x)=='VALID'
    assert status({**x,'nt_position_accepted':True,'nt_quality_source':'synthetic-current-quality'})=='INVALID'

def test_nmea0183_zero_xor_checksum_unicode_and_start_identity():
    # 47^50^54^58^54^2C^63 == 00 (hex), including the comma.
    x=actual(body='GPTXT,c')
    assert x['nt_checksum']==0;assert status(x)=='VALID'
    assert status({**x,'nt_sentence':x['nt_sentence'].replace('TXT','T€T')})=='INVALID'
    assert status({**x,'nt_start':'!'})=='INVALID'

def test_nmea0183_length82_is_sentence_not_application_or_wrapped_wire_and_high_precision_qualified():
    x=actual(body='GPTXT,'+'a'*70);assert x['nt_sentence_bytes']==82;assert status(x)=='VALID'
    x=actual(body='GPTXT,'+'a'*71);assert status(x)=='INVALID'
    x.update(nt_limit82=False,nt_high_precision=True,nt_compatibility=False);assert status(x)=='VALID'
    assert status({**x,'nt_compatibility':True})=='INVALID'
    assert status({**x,'nt_limit82':True})=='INVALID'
    x.update(payload_bytes=5000,nt_tag_present=True,nt_wrapper_source='synthetic-actual-tag',nt_wrapper_bytes=24,
      nt_wrapped_bytes=x['nt_sentence_bytes']+24);assert status(x)=='VALID'
    assert status({**x,'nt_wrapped_bytes':x['nt_sentence_bytes']})=='INVALID'

def test_nmea0183_proprietary_address_is_qualified_manufacturer_not_integer_pgn():
    x=actual(body='PUBX,00,123');x.pop('nt_talker_id');x.pop('nt_formatter')
    x.update(nt_sentence_form='PROPRIETARY',nt_manufacturer='UBX');assert status(x)=='VALID'
    assert status({**x,'nt_manufacturer':'FEC'})=='INVALID'
    assert status({**x,'nt_address':'PFEC'})=='INVALID'
    y={**actual(),'nt_version':'4.30'};assert status(y)=='INVALID'
    y.update(nt_implementation='REGISTERED',nt_registered_source='synthetic-actual4.30-edition');assert status(y)=='VALID'

@pytest.mark.parametrize('version,code',[('2.1',21),('2.3',23),('4.00',40),('4.10',41),('4.11',42)])
def test_nmea0183_current_ublox_version_codes_are_decimal_not_old_hex_fields(version,code):
    x={**actual(),'nt_version':version,'nt_version_code':code};assert status(x)=='VALID'
    assert status({**x,'nt_version_code':int(f'{code}',16)})=='INVALID'
    assert status({**x,'nt_version_code':0x4b})=='INVALID'

def test_nmea0183_multi_gnss_automatic_override_and_gsv_scope_not_all_gp():
    x=actual(body='GNZDA,141644.00,22,03,2002,00,00');x.update(nt_gnss='MULTI',nt_talker_selection='AUTO')
    assert status(x)=='VALID';assert status({**x,'nt_talker_id':'GP'})=='INVALID'
    x=actual(body='GPZDA,141644.00,22,03,2002,00,00');x.update(nt_gnss='MULTI',nt_talker_selection='OVERRIDE');assert status(x)=='VALID'
    x=actual(body='GAGSV,1,1,0');x.update(nt_gnss='MULTI',nt_talker_selection='AUTO');assert status(x)=='VALID'
    x.update(nt_gnss='GALILEO',nt_numbering='STRICT',nt_version='2.3',nt_version_code=23);assert status(x)=='INVALID'
    x.update(nt_version='4.10',nt_version_code=41);assert status(x)=='VALID'
    x=actual(body='GPZDA,141644.00,22,03,2002,00,00')
    x.update(nt_gnss='QZSS',nt_talker_selection='AUTO',nt_numbering='EXTENDED',nt_version='4.10',nt_version_code=41)
    assert status(x)=='VALID'
    x=actual(body='GQZDA,141644.00,22,03,2002,00,00')
    x.update(nt_gnss='QZSS',nt_talker_selection='AUTO',nt_numbering='EXTENDED',nt_version='4.10',nt_version_code=41)
    assert status(x)=='INVALID'

def test_nmea0183_output_disabled_message_not_whole_port_and_all_stream_bandwidth():
    x={**actual(),'nt_measurement_ms':1000,'nt_navigation_multiplier':2,'nt_message_divisor':3,'nt_output_period_ms':6000,
      'nt_total_stream_bytes_s':480,'nt_total_stream_bits_s':4800,'nt_other_protocols_enabled':True}
    assert status(x)=='VALID'
    for patch in({'nt_output_period_ms':1000},{'nt_navigation_multiplier':128},{'nt_measurement_ms':65536},
      {'nt_total_stream_bytes_s':481,'nt_total_stream_bits_s':4810},{'nt_total_stream_bits_s':480}):assert status({**x,**patch})=='INVALID'
    x.pop('nt_output_period_ms');x.update(nt_message_divisor=0,nt_message_enabled=False,nt_nmea_output_enabled=True);assert status(x)=='VALID'
    assert status({**x,'nt_message_enabled':True})=='INVALID'

@pytest.mark.parametrize('binding',['TCP_STREAM','UDP_DATAGRAM','USB_HOST','I2C_HOST','SPI_HOST'])
def test_nmea0183_registered_lower_layer_does_not_acquire4800_or_ethernet_rate(binding):
    x=actual(binding);assert status(x)=='VALID'
    for rate in(4800,38400,250000,100000000):assert status({**x,'bitrate_bps':rate})=='INVALID'
    x.pop('nt_wrapper_source');assert status(x)=='UNVERIFIED'

@pytest.mark.parametrize('port,rate',[('IN1',38400),('IN4',38400),('IN5',4800),('IN8',4800),('OUT1',115200),('OUT2',38400),('OUT6',38400),('SERIAL',115200)])
def test_nmea0183_mux_port_specific_limits_and_direction(port,rate):
    x=mux(port,rate);assert status(x)=='VALID'
    assert status({**x,'bitrate_bps':rate+1,'nt_rx_baud_bps':rate+1})=='INVALID'
    if port!='SERIAL':assert status({**x,'nt_role':'TALKER'if port.startswith('IN')else'LISTENER'})=='INVALID'

def test_nmea0183_mux_electrical_testload_transient_duration_and_operating_not_storage():
    x={**mux(),'nt_supply_v':9,'nt_temperature_c':-15,'nt_humidity_percent':80,
      'nt_output_load_ohm':100,'nt_diff_output_v':2.1,'nt_output_current_ma':20,
      'nt_electrical_source':'synthetic-installed-qualification','nt_input_v':35,'nt_input_exposure_ms':999,
      'nt_input_isolation_v':2500,'nt_output_isolation_v':1000};assert status(x)=='VALID'
    for patch in({'nt_supply_v':8.9},{'nt_temperature_c':-40},{'nt_temperature_c':56},{'nt_humidity_percent':81},
      {'nt_diff_output_v':2},{'nt_output_current_ma':20.1},{'nt_input_exposure_ms':1000},{'nt_output_isolation_v':1500}):assert status({**x,**patch})=='INVALID'
    x.update(nt_input_v=15,nt_input_exposure_ms=1000);assert status(x)=='VALID'
    x.update(nt_port='SERIAL',nt_output_isolation_v=1500);assert status(x)=='VALID'

def test_nmea0183_confirmed_uart_rate_long_highprecision_sentence_and_invalid_data_flag_preserved():
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    x=actual('DEVICE_UART',body='GPTXT,'+'a'*90);x.update(bitrate_bps=9600,nt_rx_baud_bps=9600,
      nt_limit82=False,nt_high_precision=True,nt_compatibility=False,nt_freshness_status='INVALID',nt_invalid_fix_output=True)
    group={'values':x,'provenance':{k:{'source':'USER_CONFIRMED','status':'CONFIRMED','value':v}for k,v in x.items()}}
    parameters={'technology':'nmea0183','technology_parameters':{'nmea0183':group}}
    service=WorkflowStatusService(current_project_id());service.save_parameters(parameters);assert service.get()['parameters']==parameters
    bad=deepcopy(parameters);bad['technology_parameters']['nmea0183']['values']['mtu_bytes']=1500
    with pytest.raises(ValueError):service.save_parameters(bad)
    assert service.get()['parameters']==parameters
