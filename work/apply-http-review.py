from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-http-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[k] for k in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['http_version','http_transport','http_binding_source','http_implementation_source','http_schedule_source']
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':when or {},'parameter':key,**kwargs})
for version in ('HTTP_1_1','HTTP_2','HTTP_3'):
    scope={'http_version':version}
    for key,_,_,_,_,_,_ in declarations:
        if key.startswith('http2_') and version!='HTTP_2' or key.startswith('http3_') and version!='HTTP_3':
            rule(key,scope,allowed=[])
rule('http_transport',{'http_version':'HTTP_2'},allowed=['TCP'])
rule('http_transport',{'http_version':'HTTP_3'},allowed=['QUIC_V1'])
rule('http_tls_version',{'http_version':'HTTP_3'},allowed=['TLS_1_3'])
rule('http_security_source',{'http_version':'HTTP_3'},required=True)
rule('http3_quic_source',{'http_version':'HTTP_3'},required=True)
rule('http_security_source',{'http_scheme':'https'},required=True)
rule('http_tls_version',{'http_scheme':'https'},required=True)
rule('http_method',{'http_message_kind':'REQUEST'},required=True)
rule('http_status',{'http_message_kind':'RESPONSE'},required=True)
rule('http_status',{'http_message_kind':'REQUEST'},allowed=[])
rule('http_framing',{'http_message_kind':'REQUEST'},allowed=['NONE','CONTENT_LENGTH','CHUNKED','MULTIPLEXED'])
rule('http_method',{'http_target_form':'AUTHORITY'},allowed=['CONNECT'])
rule('http_method',{'http_target_form':'ASTERISK'},allowed=['OPTIONS'])
rule('http_target_form',{'http_version':'HTTP_1_1','http_method':'CONNECT','http_message_kind':'REQUEST'},allowed=['AUTHORITY'])
for version in ('HTTP_2','HTTP_3'):
    scope={'http_version':version}
    rule('http_target_form',scope,allowed=[])
    rule('http_transfer_encoding',scope,allowed=['NONE'])
    rule('http_framing',scope,allowed=['NONE','MULTIPLEXED','TUNNEL'])
rule('http_content_length_present',when_present=['http_content_length'],allowed=[True])
rule('http_content_length',{'http_content_length_present':False},allowed=[])
rule('http_content_length',{'http_content_length_present':True},required=True)
rule('http_length_semantics',{'http_content_length_present':True},required=True)
rule('http_content_length',{'http_length_semantics':'MESSAGE_BODY'},equal_decimal_parameter='http_body_bytes')
for transfer in ('CHUNKED','OTHER'):
    rule('http_content_length_present',{'http_transfer_encoding':transfer},allowed=[False])
    rule('http_content_length',{'http_transfer_encoding':transfer},allowed=[])
    rule('http_transfer_source',{'http_transfer_encoding':transfer},required=True)
rule('http_transfer_encoding',{'http_version':'HTTP_1_1','http_framing':'CHUNKED'},allowed=['CHUNKED'])
rule('http_transfer_encoding',{'http_version':'HTTP_1_1','http_framing':'CHUNKED'},required=True)
rule('http_content_length_present',{'http_version':'HTTP_1_1','http_framing':'CONTENT_LENGTH'},allowed=[True])
rule('http_content_length_present',{'http_version':'HTTP_1_1','http_framing':'CONTENT_LENGTH'},required=True)
rule('http_body_bytes',{'http_message_kind':'RESPONSE','http_method':'HEAD'},allowed=['0'])
for status in (204,205,304): rule('http_body_bytes',{'http_message_kind':'RESPONSE','http_status':status},allowed=['0'])
rule('http_body_bytes',{'http_message_kind':'RESPONSE'},when_ranges={'http_status':[100,199]},allowed=['0'])
for key in ('http_content_length','http_transfer_encoding'):
    for status in (204,): rule(key,{'http_message_kind':'RESPONSE','http_status':status},allowed=[] if key=='http_content_length' else ['NONE'])
    rule(key,{'http_message_kind':'RESPONSE'},when_ranges={'http_status':[100,199]},allowed=[] if key=='http_content_length' else ['NONE'])
rule('http_length_semantics',{'http_message_kind':'REQUEST'},allowed=['MESSAGE_BODY'])
rule('http_content_length',{'http_message_kind':'RESPONSE','http_method':'CONNECT'},when_ranges={'http_status':[200,299]},allowed=[])
rule('http_transfer_encoding',{'http_message_kind':'RESPONSE','http_method':'CONNECT'},when_ranges={'http_status':[200,299]},allowed=['NONE'])
rule('http_transition_source',{'http_transition_optimistic':True},required=True)
rule('http_retry_source',when_positive=['http_retry_limit'],required=True)
h2={'http_version':'HTTP_2'}
rule('http2_frame_bytes',h2,equal_sum=[{'parameter':'http2_frame_header_bytes'},{'parameter':'http2_frame_payload_bytes'}])
rule('http2_frame_payload_bytes',h2,maximum_parameter='http2_max_frame_size')
for typ in ('DATA','HEADERS','PRIORITY','RST_STREAM','PUSH_PROMISE','CONTINUATION'):
    rule('http2_stream_id',{**h2,'http2_frame_type':typ},exclusive_minimum=0)
for typ in ('SETTINGS','PING','GOAWAY'): rule('http2_stream_id',{**h2,'http2_frame_type':typ},allowed=[0])
for typ,size in [('PING',8),('PRIORITY',5),('RST_STREAM',4),('WINDOW_UPDATE',4)]:
    rule('http2_frame_payload_bytes',{**h2,'http2_frame_type':typ},allowed=[size])
rule('http2_frame_payload_bytes',{**h2,'http2_frame_type':'GOAWAY'},minimum=8)
rule('http2_frame_payload_bytes',{**h2,'http2_frame_type':'SETTINGS'},multiple_of=6)
for key in ('http2_current_stream_window','http2_current_connection_window'):
    rule('http2_frame_payload_bytes',{**h2,'http2_frame_type':'DATA'},when_positive=['http2_frame_payload_bytes'],maximum_parameter=key)
for padded,offset in [(False,0),(True,1)]:
    rule('http2_frame_payload_bytes',{**h2,'http2_frame_type':'DATA','http2_pad_length_present':padded},
         equal_sum=[{'parameter':'http2_data_bytes'},{'parameter':'http2_padding_bytes'}],equal_sum_offset=offset)
rule('http2_padding_bytes',{**h2,'http2_pad_length_present':False},allowed=[0])
rule('http2_enable_push',{**h2,'http_role':'SERVER'},allowed=[0])
for streamkind in ('QPACK_ENCODER','QPACK_DECODER'):
    rule('http3_frame_type',{'http_version':'HTTP_3','http3_stream_kind':streamkind},allowed=[])
rule('http3_frame_type',{'http_version':'HTTP_3','http3_stream_kind':'CONTROL'},forbidden=['0','1','5'])
for streamkind in ('REQUEST','PUSH'):
    rule('http3_frame_type',{'http_version':'HTTP_3','http3_stream_kind':streamkind},forbidden=['3','4','7','13'])
constraints.extend([{'allowed': ['MESSAGE_BODY'],
  'parameter': 'http_length_semantics',
  'when': {'http_message_kind': 'RESPONSE'},
  'when_not': {'http_method': 'HEAD', 'http_status': 304}},
 {'parameter': 'http_transition_token', 'required': True, 'when': {'http_transition_optimistic': True}},
 {'allowed': [False],
  'parameter': 'http_transition_optimistic',
  'when': {'http_transition_token': 'WEBSOCKET'}},
 {'allowed': [False],
  'parameter': 'http_transition_optimistic',
  'when': {'http_transition_token': 'CONNECT_UDP', 'http_version': 'HTTP_1_1'}},
 {'allowed': [False],
  'parameter': 'http_transition_optimistic',
  'when': {'http_transition_token': 'CONNECT_IP', 'http_version': 'HTTP_1_1'}},
 {'allowed': [True],
  'parameter': 'http_wait_success',
  'required': True,
  'when': {'http_connect_untrusted': True,
           'http_transition_token': 'CONNECT_TCP',
           'http_version': 'HTTP_1_1'},
  'when_not': {'http_connection_close': True}},
 {'allowed': [True],
  'parameter': 'http_connection_close',
  'required': True,
  'when': {'http_role': 'PROXY',
           'http_transition_rejected': True,
           'http_transition_token': 'CONNECT_TCP',
           'http_version': 'HTTP_1_1'}},
 {'forbidden': ['5'],
  'parameter': 'http3_frame_type',
  'when': {'http_role': 'CLIENT', 'http_version': 'HTTP_3'}},
 {'forbidden': ['13'],
  'parameter': 'http3_frame_type',
  'when': {'http_role': 'SERVER', 'http_version': 'HTTP_3'}}])
sem={'rate_model':{'type':'APPLICATION_TRANSPORT_DEPENDENT','fields':[]},'required_parameters':required,
     'native_parameter_prefixes':['http_','http2_','http3_'],
     'mechanisms':{'access':['ACTUAL_HTTP1_ORDERING_HTTP2_STREAMS_OR_HTTP3_QUIC'],
                   'integrity':['ACTUAL_TRANSPORT_TLS_QUIC_AND_APPLICATION_ACCEPTANCE'],
                   'scope':['VERSION_SPECIFIC_APPLICATION_NOT_UNIVERSAL_ETHERNET_TCP_STACK']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['hart'] =",f"TECHNOLOGY_SEMANTICS['http'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['hart'] =",1)
proposal={'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'No own physical rate or universal HTTP65535-byte message cap. Version-specific initialsettings proposals only until actual peer advertisements; actual explicit transport binding required.'}
text=text.replace("    'hart':",f"    'http': {proposal!r},\n    'hart':",1)
text=text.replace("'generic_serial','gpio','hart'} else", "'generic_serial','gpio','hart','http'} else",1)
text=text.replace('("http", "HTTP", "iot_wireless", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "ethernet_or_wireless_interface", ("ethernet", "ip", "tcp", "http"), None, 65535, ("objects", "streams", "request_response", "segmentation"), False)',
 '("http", "HTTP", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "RAW_DATA"), "explicit_http_transport_binding", (), None, None, ("objects", "streams", "request_response", "segmentation"), False)',1)
block=f'''    if technology_id == 'http':
        source=REVIEW_RATE_PROPOSALS['http']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual NIS application chunk octets; whole HTTP content/message/framing differ. No8-byte or65535-byte protocol default.')
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('http_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            field_source=('https://www.rfc-editor.org/rfc/rfc9113.html' if key.startswith('http2_') else
                'https://www.rfc-editor.org/rfc/rfc9204.html' if key.startswith('http3_qpack') else
                'https://www.rfc-editor.org/rfc/rfc9114.html' if key.startswith('http3_') else
                'https://www.rfc-editor.org/rfc/rfc9931.html' if key.startswith('http_transition') else source['source'])
            native.update(required=key in TECHNOLOGY_SEMANTICS['http']['required_parameters'],integer=kind=='number' and unit!='ms',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=field_source,source_revision=source['source_revision'])
            if key.startswith('http2_'): native['schema_when']={{'http_version':'HTTP_2'}}
            if key.startswith('http3_'): native['schema_when']={{'http_version':'HTTP_3'}}
            if key in {{'http_content_length','http_body_bytes','http_wire_message_bytes'}}: native['pattern']=r'[0-9]+'
            if key.startswith('http3_') and kind=='text' and key!='http3_quic_source':
                native.update(pattern=r'0|[1-9][0-9]*',integer_text_maximum=4611686018427387903)
            if key=='http_method': native['pattern']=r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
            if key=='http_origin': native.update(format='ABSOLUTE_URI',allowed_schemes=['http','https'])
            if key in {{'http2_frame_header_bytes','http2_max_frame_size','http2_header_table_size','http2_initial_window_size'}}:
                value={{'http2_frame_header_bytes':9,'http2_max_frame_size':16384,'http2_header_table_size':4096,'http2_initial_window_size':65535}}[key]
                when={{'http_version':'HTTP_2'}}
                if key!='http2_frame_header_bytes': when['http2_settings_phase']='INITIAL_DEFAULTS'
                native.update(conditional_defaults=[{{'when':when,'value':value}}],default_status='PROPOSED_CONDITIONAL')
            if key=='http2_enable_push':
                native.update(conditional_defaults=[{{'when':{{'http_version':'HTTP_2','http2_settings_phase':'INITIAL_DEFAULTS','http_role':role}},'value':value}} for role,value in [('CLIENT',1),('SERVER',0)]],default_status='PROPOSED_CONDITIONAL')
            if key in {{'http3_qpack_max_table','http3_qpack_blocked_streams'}}:
                native.update(conditional_defaults=[{{'when':{{'http_version':'HTTP_3','http3_settings_phase':'INITIAL_1RTT'}},'value':'0'}}],default_status='PROPOSED_CONDITIONAL')
            if key=='http_port':
                native.update(conditional_defaults=[{{'when':{{'http_scheme':scheme,'http_port_explicit':False}},'value':port}} for scheme,port in [('http',80),('https',443)]],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'hart':\n        source=",block+"    if technology_id == 'hart':\n        source=",1)
path.write_text(text,encoding='utf-8')
print({'native_fields':len(declarations),'constraints':len(constraints)})
