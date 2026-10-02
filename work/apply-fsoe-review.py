from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-fsoe-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[key] for key in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
base={'fsoe_profile':'BASE_5100_1_2'}
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':{**base,**(when or {})},'parameter':key,**kwargs})
for key in ('payload_bytes','fsoe_master_safe_bytes','fsoe_slave_safe_bytes'):
    rule(key,minimum=1)
    constraints.append({'when':base,'when_greater_than':{key:1},'parameter':key,'multiple_of':2})
rule('payload_bytes',{'fsoe_direction':'MASTER_TO_SLAVE'},equal_parameter='fsoe_master_safe_bytes')
rule('payload_bytes',{'fsoe_direction':'SLAVE_TO_MASTER'},equal_parameter='fsoe_slave_safe_bytes')
rule('fsoe_crc_count',equal_expression={'ceiling':[{'product':[0.5,'payload_bytes']}]})
rule('fsoe_frame_bytes',equal_expression={'sum':['fsoe_command_bytes','payload_bytes',{'product':['fsoe_crc_count','fsoe_crc_word_bytes']},'fsoe_connection_bytes']})
rule('fsoe_frame_bytes',maximum_parameter='fsoe_pdo_capacity_bytes')
rule('fsoe_slave_address',equal_parameter='fsoe_peer_address')
rule('fsoe_master_watchdog_ms',equal_parameter='fsoe_slave_watchdog_ms')
for key in ('fsoe_master_watchdog_ms','fsoe_slave_watchdog_ms'):
    rule(key,minimum_parameter='fsoe_exchange_bound_ms')
    constraints.append({'when':base,'when_present':['fsoe_exchange_bound_ms'],'parameter':key,
                        'not_equal_parameter':'fsoe_exchange_bound_ms'})
rule('fsoe_parameter_remaining_bytes',maximum_parameter='fsoe_parameter_bytes')
rule('fsoe_data_command',{'fsoe_state':'RESET'},allowed=[])
for state in ('RESET','SESSION'):
    rule('fsoe_conn_id',{'fsoe_state':state},allowed=[0])
rule('fsoe_crc0',{'fsoe_state':'RESET'},allowed=[0])
rule('fsoe_command',{'fsoe_state':'RESET'},allowed=[42])
rule('fsoe_conn_id',{'fsoe_state':'DATA'},minimum=1)
rule('fsoe_sequence',{'fsoe_state':'DATA'},minimum=1)
rule('fsoe_parameters_accepted',{'fsoe_state':'DATA'},allowed=[True])
for meaning,cmd in (('PROCESS_DATA',54),('FAILSAFE_DATA',8)):
    rule('fsoe_command',{'fsoe_state':'DATA','fsoe_data_command':meaning},allowed=[cmd])
for key in ('fsoe_direction','fsoe_conn_id','fsoe_slave_address','fsoe_peer_address','fsoe_parameters_accepted',
            'fsoe_master_watchdog_ms','fsoe_slave_watchdog_ms','fsoe_exchange_bound_ms','fsoe_mapping_source',
            'fsoe_crc_source','fsoe_safe_output_source','fsoe_assurance_source'):
    rule(key,{'fsoe_state':'DATA'},required=True)
required=['fsoe_profile','fsoe_role','fsoe_transport_binding','fsoe_implementation_source','fsoe_connection_source','fsoe_timing_source']
sem={'rate_model':{'type':'APPLICATION_TRANSPORT_DEPENDENT','fields':[]},'required_parameters':required,
     'mechanisms':{'access':['MASTER_SLAVE_HANDSHAKE_OVER_EXPLICIT_BLACK_CHANNEL'],
       'integrity':['CRC16_PER_TWO_SAFE_OCTETS','INHERITED_CRC_VIRTUAL_SEQUENCE_SESSION_AND_CONN_ID'],
       'supervision':['BIDIRECTIONAL_WATCHDOG','SAFE_STATE_APPLICATION_DEFINED']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['foundation_fieldbus_h1'] =",f"TECHNOLOGY_SEMANTICS['fsoe'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['foundation_fieldbus_h1'] =",1)
proposal={'kind':'APPLICATION_TRANSPORT_DEPENDENT','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
 'note':'FSoE has no own bitrate, universal safe-data maximum or universal watchdog default. Base one-byte/even-block container requires configured directional data/mapping, CRC chain and endpoint watchdog. Black channel and optional enhancements need their own profiles; no automatic SIL/PL acceptance.'}
text=text.replace("    'foundation_fieldbus_h1':",f"    'fsoe': {proposal!r},\n    'foundation_fieldbus_h1':",1)
text=text.replace("'flexray','foundation_fieldbus_h1'} else", "'flexray','foundation_fieldbus_h1','fsoe'} else",1)
text=text.replace('("fsoe", "FSoE", "industrial_automation", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "ethercat_port", ("ethernet", "ethercat", "fsoe"), 100_000_000, 1486, ("safety", "time_sync"), True)',
 '("fsoe", "FSoE", "generic_networking", "APPLICATION", "PDU", ("FIELD", "STATUS", "QUALITY"), "explicit_black_channel_binding", (), None, None, ("safety", "request_response"), False)',1)
block=f'''    if technology_id == 'fsoe':
        source=REVIEW_RATE_PROPOSALS['fsoe']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(min=1,integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    schema_when={{'fsoe_profile':'BASE_5100_1_2'}},
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual selected-direction safe data: one byte or even count for reviewed base format; mapped complete container capacity is separate.')
        for key,kind,unit,options,minimum,maximum,default,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('fsoe_','').replace('_',' '),'timing' if unit=='ms' else 'physical','route',
                field_type=kind,unit=unit,options=options,minimum=minimum,maximum=maximum,
                default=default if key=='fsoe_profile' else None,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['fsoe']['required_parameters'],
                integer=kind=='number' and key!='fsoe_exchange_bound_ms',
                parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                default_status='PROPOSED' if default is not None else 'UNKNOWN',
                source=source['source'],source_revision=source['source_revision'])
            if default is not None and key!='fsoe_profile':
                native.update(conditional_defaults=[{{'when':{{'fsoe_profile':'BASE_5100_1_2'}},'value':default}}],default_status='PROPOSED_CONDITIONAL')
            if key not in TECHNOLOGY_SEMANTICS['fsoe']['required_parameters']:
                native['schema_when']={{'fsoe_profile':'BASE_5100_1_2'}}
            fields.append(native)
'''
text=text.replace("    if technology_id == 'foundation_fieldbus_h1':\n",block+"    if technology_id == 'foundation_fieldbus_h1':\n",1)
path.write_text(text,encoding='utf-8')
print({'fields':len(declarations),'constraints':len(constraints)})
