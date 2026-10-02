from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-hart-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[k] for k in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['bitrate_bps','hart_profile','hart_phy','hart_revision','hart_role','hart_binding_source','hart_device_source','hart_physical_source','hart_schedule_source']
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':when or {},'parameter':key,**kwargs})
rule('bitrate_bps',{'hart_phy':'FSK'},allowed=[1200])
rule('bitrate_bps',{'hart_phy':'C8PSK'},allowed=[9600])
for profile in ('PUBLIC_FSK_2023','FCG_FSK_2016'):
    scope={'hart_profile':profile}
    rule('hart_phy',scope,allowed=['FSK'])
    for address,size in [('SHORT',1),('LONG',5)]: rule('hart_address_bytes',{**scope,'hart_address_format':address},allowed=[size])
    rule('hart_address_bytes',scope,allowed=[1,5])
    rule('hart_preamble_bytes',scope,minimum_parameter='hart_peer_preamble_bytes')
    rule('hart_byte_count',scope,equal_sum=[{'parameter':'hart_data_bytes'},{'parameter':'hart_status_bytes'}])
    rule('hart_wire_octets',scope,equal_sum=[{'parameter':key} for key in ('hart_preamble_bytes','hart_address_bytes','hart_expansion_bytes','hart_byte_count','hart_checksum_bytes')],equal_sum_offset=3)
    rule('hart_wire_bits',scope,equal_expression={'product':['hart_wire_octets','hart_char_bits']})
    rule('hart_serialization_ms',scope,equal_ratio={'numerator_parameter':'hart_wire_bits','denominator_sum':['bitrate_bps'],'factor':1000})
    for kind,status,framecode in [('REQUEST',0,2),('RESPONSE',2,6),('BURST',2,1)]:
        when={**scope,'hart_frame_kind':kind}
        rule('hart_status_bytes',when,allowed=[status])
        for address,addressflag in [('SHORT',0),('LONG',128)]:
            rule('hart_delimiter',{**when,'hart_address_format':address},equal_expression={'sum':[addressflag+framecode,{'product':[32,'hart_expansion_bytes']}]})
    for revision in ('REV5_OR_EARLIER','REV6','REV7'):
        rule('hart_poll_address',{**scope,'hart_revision':revision},maximum=15 if revision=='REV5_OR_EARLIER' else 63)
rule('hart_frame_kind',{'hart_role':'HOST'},allowed=['REQUEST'])
rule('hart_frame_kind',{'hart_role':'FIELD_DEVICE'},allowed=['RESPONSE','BURST'])
rule('hart_frame_kind',{'hart_mode':'REQUEST_RESPONSE'},allowed=['REQUEST','RESPONSE'])
rule('hart_burst_supported',{'hart_mode':'BURST'},allowed=[True])
rule('hart_burst_supported',{'hart_mode':'BURST'},required=True)
rule('hart_burst_period_ms',exclusive_minimum=0)
rule('hart_extended_command',when_present=['hart_extended_command'],required=True)
rule('hart_command',when_present=['hart_extended_command'],allowed=[31])
rule('hart_data_bytes',when_present=['hart_extended_command'],minimum=2)
rule('payload_bytes',equal_parameter='hart_data_bytes')
fcg={'hart_profile':'FCG_FSK_2016','hart_phy':'FSK'}
for host,n in [('PRIMARY',33),('SECONDARY',41)]: rule('hart_quiet_chars',{**fcg,'hart_host_role':host},allowed=[n])
rule('hart_host_role',{**fcg,'hart_role':'HOST'},required=True)
rule('hart_gap_us',fcg,maximum_ratio={'numerator_parameter':'hart_char_bits','denominator_sum':['bitrate_bps'],'factor':1000000},exclusive_maximum_ratio=True)
rule('hart_response_start_ms',fcg,maximum_expression={'product':['hart_slave_timeout_chars',11,1000/1200]})
rule('hart_loop_supply_v',exclusive_minimum=0)
rule('hart_signal_pp_ma',exclusive_minimum=0)
rule('hart_is_source',{'hart_is_required':True},required=True)
sem={'rate_model':{'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'allowed_bps':[1200,9600]},
     'required_parameters':required,'native_parameter_prefixes':['hart_'],
     'mechanisms':{'access':['ACTUAL_HALF_DUPLEX_DUAL_HOST_AND_BURST_ARBITRATION'],
                   'integrity':['QUALIFIED_FSK_ODD_PARITY_AND_XOR_CHECKSUM_NOT_AUTHENTICATION'],
                   'scope':['WIRED_FSK_OR_EXPLICIT_C8PSK_NOT_WIRELESSHART_HARTIP']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['gpio'] =",f"TECHNOLOGY_SEMANTICS['hart'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['gpio'] =",1)
proposal={'kind':'STANDARD_BASELINE','default_bps':1200,'default_basis':'WIRED_FSK_BASELINE','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'Wired FSK baseline1200bit/s proposal. C8PSK requires explicit actual mode9600 and own codec/PHY evidence. No automatic HART-IP/WirelessHART transport or device identity.'}
text=text.replace("    'gpio':",f"    'hart': {proposal!r},\n    'gpio':",1)
text=text.replace("'generic_serial','gpio'} else", "'generic_serial','gpio','hart'} else",1)
text=text.replace('("hart", "HART", "process_industry", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "hart_interface", (), 1_200, 255, ("request_response",), False)',
 '("hart", "HART (wired)", "generic_networking", "INDUSTRY_PROFILE", "TELEGRAM", ("FIELD", "STATUS", "QUALITY"), "explicit_hart_modem_loop", (), None, 255, ("request_response",), False)',1)
qualified={'hart_profile':['PUBLIC_FSK_2023','FCG_FSK_2016'],'hart_phy':['FSK']}
qualified_keys={'hart_preamble_bytes','hart_peer_preamble_bytes','hart_expanded_device_type','hart_device_id','hart_checksum_bytes','hart_char_bits','hart_loop_load_ohms'}
block=f'''    if technology_id == 'hart':
        source=REVIEW_RATE_PROPOSALS['hart']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual encoded HART data excl response status; count/whole frame differ, no8-byte default.')
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('hart_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['hart']['required_parameters'],
                integer=kind=='number' and unit not in {{'ms','us','Ohm','V','mA','pF'}},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {qualified_keys!r}: native['schema_when']={qualified!r}
            if key in {{'hart_slave_timeout_chars','hart_hold_chars','hart_link_grant_chars','hart_quiet_chars'}}:
                native.update(schema_when={{'hart_profile':['FCG_FSK_2016'],'hart_phy':['FSK']}},source={data['TIMERS']!r},source_revision='FieldComm character-time support article2016-11-11')
            if key=='hart_expanded_device_type': native['schema_when']['hart_revision']=['REV6','REV7']
            if key in {{'hart_phy','hart_char_bits','hart_expansion_bytes','hart_checksum_bytes'}}:
                value={{'hart_phy':'FSK','hart_char_bits':11,'hart_expansion_bytes':0,'hart_checksum_bytes':1}}[key]
                native.update(conditional_defaults=[{{'when':{{'hart_profile':'PUBLIC_FSK_2023'}},'value':value}}],default_status='PROPOSED_CONDITIONAL')
            if key in {{'hart_slave_timeout_chars','hart_hold_chars','hart_link_grant_chars'}}:
                value={{'hart_slave_timeout_chars':28,'hart_hold_chars':2,'hart_link_grant_chars':8}}[key]
                native.update(conditional_defaults=[{{'when':{{'hart_profile':'FCG_FSK_2016','hart_phy':'FSK'}},'value':value}}],default_status='PROPOSED_CONDITIONAL')
            if key=='hart_quiet_chars':
                native.update(conditional_defaults=[{{'when':{{'hart_profile':'FCG_FSK_2016','hart_phy':'FSK','hart_host_role':host}},'value':n}} for host,n in [('PRIMARY',33),('SECONDARY',41)]],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'gpio':\n        source=",block+"    if technology_id == 'gpio':\n        source=",1)
path.write_text(text,encoding='utf-8')
print({'native_fields':len(declarations),'constraints':len(constraints)})
