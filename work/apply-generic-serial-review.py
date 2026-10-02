from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-generic-serial-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[k] for k in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['gs_mode','gs_transport_binding','gs_implementation_source','gs_framing_source']
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':when or {},'parameter':key,**kwargs})
uart={'gs_mode':'ASYNC_UART'}
uart_fields=[key for key,_,_,_,_,_,_ in declarations if key not in {*required,'gs_clock_hz','gs_cdc_line_coding_role','gs_framing','gs_message_bytes','gs_max_message_bytes'}]
for mode in ('SYNC_SERIAL','USB_CDC','CUSTOM_STREAM'):
    for key in uart_fields: rule(key,{'gs_mode':mode},allowed=[])
for mode in ('ASYNC_UART','USB_CDC','CUSTOM_STREAM'): rule('gs_clock_hz',{'gs_mode':mode},allowed=[])
for mode in ('ASYNC_UART','SYNC_SERIAL','CUSTOM_STREAM'): rule('gs_cdc_line_coding_role',{'gs_mode':mode},allowed=[])
rule('gs_uart_profile',uart,required=True)
rule('gs_baud_rate',uart,required=True)
rule('gs_clock_hz',{'gs_mode':'SYNC_SERIAL'},required=True)
rule('gs_cdc_line_coding_role',{'gs_mode':'USB_CDC'},required=True)
rule('gs_peer_baud_rate',uart,equal_parameter='gs_baud_rate')
for profile in ('TB3216_8N1','AVR_FRAME_FORMATS'):
    when={**uart,'gs_uart_profile':profile}
    for key,allowed in [('gs_data_bits',list(range(5,10))),('gs_parity',['NONE','EVEN','ODD']),('gs_start_bits',[1]),('gs_stop_bits',[1,2])]:
        rule(key,when,allowed=allowed)
    for parity,extra in [('NONE',0),('EVEN',1),('ODD',1)]:
        rule('gs_char_bits',{**when,'gs_parity':parity},equal_sum=[{'parameter':key} for key in ('gs_start_bits','gs_data_bits','gs_stop_bits')],equal_sum_offset=extra)
    rule('gs_wire_bits',when,equal_expression={'product':['gs_char_bits','gs_encoded_characters']})
    rule('gs_serialization_us',when,equal_ratio={'numerator_parameter':'gs_wire_bits','denominator_sum':['gs_baud_rate'],'factor':1000000})
    rule('gs_wire_bound_us',when,minimum_expression={'sum':['gs_serialization_us','gs_gap_bound_us','gs_flow_bound_us']})
for key,value in [('gs_data_bits',8),('gs_parity','NONE'),('gs_start_bits',1),('gs_stop_bits',1),('gs_char_bits',10)]:
    rule(key,{**uart,'gs_uart_profile':'TB3216_8N1'},allowed=[value])
rule('gs_message_bytes',maximum_parameter='gs_max_message_bytes')
sem={'rate_model':{'type':'APPLICATION_TRANSPORT_DEPENDENT','fields':[]},'required_parameters':required,'native_parameter_prefixes':['gs_'],
     'mechanisms':{'access':['EXPLICIT_SERIAL_PORT_IMPLEMENTATION_AND_FRAMING'],
                   'integrity':['ACTUAL_UART_PARITY_AND_APPLICATION_FRAME_INTEGRITY_SEPARATE'],
                   'scope':['GENERIC_STREAM_NOT_UNIVERSAL_UART_USB_OR_SYNCHRONOUS_BUS']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['generic_can'] =",f"TECHNOLOGY_SEMANTICS['generic_serial'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['generic_can'] =",1)
proposal={'kind':'CONFIGURED_TRANSPORT_PROFILE','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'Generic Serial has no universal physical rate. Explicit async TB3216 tutorial profile has conditional9600/8N1 proposals; sync and USB CDC require their own actual bound implementation.'}
text=text.replace("    'generic_can':",f"    'generic_serial': {proposal!r},\n    'generic_can':",1)
text=text.replace("'fsoe','generic_can'} else", "'fsoe','generic_can','generic_serial'} else",1)
text=text.replace('("generic_serial", "Generic Serial", "custom", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "serial_port", (), None, 65535, ("streams",), False)',
 '("generic_serial", "Generic Serial", "generic_networking", "DATA_LINK", "STREAM_CHUNK", ("RAW_DATA",), "explicit_serial_transport_binding", (), None, None, ("streams",), False)',1)
block=f'''    if technology_id == 'generic_serial':
        source=REVIEW_RATE_PROPOSALS['generic_serial']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual qualified API stream-chunk or application octets, not UART character/wire count. No universal8-byte default or65535 maximum.')
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('gs_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['generic_serial']['required_parameters'],
                integer=kind=='number' and key not in {{'gs_stop_bits','gs_char_bits','gs_serialization_us','gs_gap_bound_us','gs_flow_bound_us','gs_wire_bound_us'}},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            proposals={{'gs_baud_rate':9600,'gs_data_bits':8,'gs_parity':'NONE','gs_start_bits':1,'gs_stop_bits':1,'gs_char_bits':10}}
            if key in proposals:
                native.update(conditional_defaults=[{{'when':{{'gs_mode':'ASYNC_UART','gs_uart_profile':'TB3216_8N1'}},'value':proposals[key]}}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'generic_can':\n",block+"    if technology_id == 'generic_can':\n",1)
path.write_text(text,encoding='utf-8')
print({'fields':len(declarations),'constraints':len(constraints)})
